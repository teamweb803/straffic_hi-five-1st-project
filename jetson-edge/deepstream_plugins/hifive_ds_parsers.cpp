#include <algorithm>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "nvdsinfer_custom_impl.h"

namespace {

constexpr int kPlateClassId = 0;
constexpr int kBlankIndex = 0;

size_t volume(const NvDsInferDims& dims) {
    size_t v = 1;
    for (unsigned int i = 0; i < dims.numDims; ++i) {
        const unsigned int dim = dims.d[i] == 0U ? 1U : dims.d[i];
        v *= static_cast<size_t>(dim);
    }
    return v;
}

const float* asFloat(const NvDsInferLayerInfo& layer) {
    return static_cast<const float*>(layer.buffer);
}

std::string layerName(const NvDsInferLayerInfo& layer) {
    return layer.layerName ? std::string(layer.layerName) : std::string();
}

bool nameContains(const NvDsInferLayerInfo& layer, const char* token) {
    return layerName(layer).find(token) != std::string::npos;
}

int hexValue(char c) {
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    return -1;
}

bool parseUnicodeEscape(const std::string& body, size_t pos, uint32_t& codepoint) {
    if (pos + 4 >= body.size()) {
        return false;
    }
    codepoint = 0;
    for (size_t i = 1; i <= 4; ++i) {
        const int value = hexValue(body[pos + i]);
        if (value < 0) {
            return false;
        }
        codepoint = (codepoint << 4) | static_cast<uint32_t>(value);
    }
    return true;
}

void appendUtf8(std::string& out, uint32_t codepoint) {
    if (codepoint <= 0x7F) {
        out.push_back(static_cast<char>(codepoint));
    } else if (codepoint <= 0x7FF) {
        out.push_back(static_cast<char>(0xC0 | (codepoint >> 6)));
        out.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    } else if (codepoint <= 0xFFFF) {
        out.push_back(static_cast<char>(0xE0 | (codepoint >> 12)));
        out.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (codepoint >> 18)));
        out.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    }
}

bool isNormalized(float value) {
    return value >= 0.0F && value <= 1.5F;
}

float scaleCoord(float value, int size) {
    return isNormalized(value) ? value * static_cast<float>(size) : value;
}

NvDsInferObjectDetectionInfo makeObject(
    float x1,
    float y1,
    float x2,
    float y2,
    float confidence,
    const NvDsInferNetworkInfo& networkInfo) {
    x1 = scaleCoord(x1, static_cast<int>(networkInfo.width));
    y1 = scaleCoord(y1, static_cast<int>(networkInfo.height));
    x2 = scaleCoord(x2, static_cast<int>(networkInfo.width));
    y2 = scaleCoord(y2, static_cast<int>(networkInfo.height));

    x1 = std::max(0.0F, std::min(x1, static_cast<float>(networkInfo.width - 1)));
    y1 = std::max(0.0F, std::min(y1, static_cast<float>(networkInfo.height - 1)));
    x2 = std::max(0.0F, std::min(x2, static_cast<float>(networkInfo.width - 1)));
    y2 = std::max(0.0F, std::min(y2, static_cast<float>(networkInfo.height - 1)));

    NvDsInferObjectDetectionInfo obj{};
    obj.classId = kPlateClassId;
    obj.detectionConfidence = confidence;
    obj.left = std::min(x1, x2);
    obj.top = std::min(y1, y2);
    obj.width = std::abs(x2 - x1);
    obj.height = std::abs(y2 - y1);
    return obj;
}

void addIfValid(
    std::vector<NvDsInferObjectDetectionInfo>& objects,
    const NvDsInferObjectDetectionInfo& obj,
    const NvDsInferParseDetectionParams& detectionParams) {
    const float threshold = detectionParams.perClassPreclusterThreshold[kPlateClassId];
    if (obj.detectionConfidence < threshold) {
        return;
    }
    if (obj.width < 1.0F || obj.height < 1.0F) {
        return;
    }
    objects.push_back(obj);
}

const NvDsInferLayerInfo* findLayerByLastDim(
    const std::vector<NvDsInferLayerInfo>& layers,
    int lastDim) {
    for (const auto& layer : layers) {
        const auto& dims = layer.inferDims;
        if (dims.numDims > 0 && static_cast<int>(dims.d[dims.numDims - 1]) == lastDim) {
            return &layer;
        }
    }
    return nullptr;
}

const NvDsInferLayerInfo* findLayerByName(
    const std::vector<NvDsInferLayerInfo>& layers,
    const char* token) {
    for (const auto& layer : layers) {
        if (nameContains(layer, token)) {
            return &layer;
        }
    }
    return nullptr;
}

bool parseSplitNms(
    const std::vector<NvDsInferLayerInfo>& layers,
    const NvDsInferNetworkInfo& networkInfo,
    const NvDsInferParseDetectionParams& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objects) {
    const NvDsInferLayerInfo* boxesLayer = findLayerByName(layers, "box");
    if (boxesLayer == nullptr) {
        boxesLayer = findLayerByLastDim(layers, 4);
    }
    const NvDsInferLayerInfo* scoresLayer = findLayerByName(layers, "score");
    const NvDsInferLayerInfo* classesLayer = findLayerByName(layers, "class");
    const NvDsInferLayerInfo* numLayer = findLayerByName(layers, "num");
    if (boxesLayer == nullptr || scoresLayer == nullptr) {
        return false;
    }

    const float* boxes = asFloat(*boxesLayer);
    const float* scores = asFloat(*scoresLayer);
    const float* classes = classesLayer ? asFloat(*classesLayer) : nullptr;
    const int maxBoxes = static_cast<int>(volume(boxesLayer->inferDims) / 4);
    int count = maxBoxes;
    if (numLayer != nullptr && volume(numLayer->inferDims) > 0) {
        count = std::min(maxBoxes, static_cast<int>(std::round(asFloat(*numLayer)[0])));
    }

    for (int i = 0; i < count; ++i) {
        const int classId = classes ? static_cast<int>(std::round(classes[i])) : kPlateClassId;
        if (classId != kPlateClassId) {
            continue;
        }
        const float* b = boxes + i * 4;
        addIfValid(
            objects,
            makeObject(b[0], b[1], b[2], b[3], scores[i], networkInfo),
            detectionParams);
    }
    return true;
}

bool parsePackedRows(
    const NvDsInferLayerInfo& layer,
    const NvDsInferNetworkInfo& networkInfo,
    const NvDsInferParseDetectionParams& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objects) {
    const auto& dims = layer.inferDims;
    if (dims.numDims <= 0) {
        return false;
    }
    const float* data = asFloat(layer);
    const size_t total = volume(dims);
    const int rowWidth = dims.d[dims.numDims - 1];
    if (rowWidth < 5 || total < static_cast<size_t>(rowWidth)) {
        return false;
    }

    const int rows = static_cast<int>(total / rowWidth);
    for (int i = 0; i < rows; ++i) {
        const float* row = data + i * rowWidth;
        const float confidence = row[4];
        const int classId = rowWidth >= 6 ? static_cast<int>(std::round(row[5])) : kPlateClassId;
        if (classId != kPlateClassId) {
            continue;
        }

        float x1 = row[0];
        float y1 = row[1];
        float x2 = row[2];
        float y2 = row[3];
        if (x2 <= x1 || y2 <= y1) {
            const float cx = row[0];
            const float cy = row[1];
            const float w = row[2];
            const float h = row[3];
            x1 = cx - w / 2.0F;
            y1 = cy - h / 2.0F;
            x2 = cx + w / 2.0F;
            y2 = cy + h / 2.0F;
        }
        addIfValid(objects, makeObject(x1, y1, x2, y2, confidence, networkInfo), detectionParams);
    }
    return true;
}

bool parseTransposedRows(
    const NvDsInferLayerInfo& layer,
    const NvDsInferNetworkInfo& networkInfo,
    const NvDsInferParseDetectionParams& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objects) {
    const auto& dims = layer.inferDims;
    if (dims.numDims <= 0) {
        return false;
    }
    const int channels = dims.numDims >= 2 ? dims.d[dims.numDims - 2] : 0;
    const int rows = dims.d[dims.numDims - 1];
    if (channels < 5 || rows <= 0) {
        return false;
    }
    const float* data = asFloat(layer);
    for (int i = 0; i < rows; ++i) {
        const float cx = data[0 * rows + i];
        const float cy = data[1 * rows + i];
        const float w = data[2 * rows + i];
        const float h = data[3 * rows + i];
        const float confidence = data[4 * rows + i];
        addIfValid(
            objects,
            makeObject(cx - w / 2.0F, cy - h / 2.0F, cx + w / 2.0F, cy + h / 2.0F, confidence, networkInfo),
            detectionParams);
    }
    return true;
}

std::vector<std::string> parseVocabJson(const std::string& body) {
    std::vector<std::string> vocab;
    const size_t key = body.find("\"vocab\"");
    if (key == std::string::npos) {
        return vocab;
    }
    const size_t begin = body.find('[', key);
    const size_t end = body.find(']', begin);
    if (begin == std::string::npos || end == std::string::npos || end <= begin) {
        return vocab;
    }
    bool inString = false;
    bool escape = false;
    std::string value;
    for (size_t i = begin + 1; i < end; ++i) {
        const char c = body[i];
        if (!inString) {
            if (c == '"') {
                inString = true;
                value.clear();
            }
            continue;
        }
        if (escape) {
            if (c == 'u') {
                uint32_t codepoint = 0;
                if (parseUnicodeEscape(body, i, codepoint)) {
                    appendUtf8(value, codepoint);
                    i += 4;
                } else {
                    value.push_back(c);
                }
            } else if (c == 'n') {
                value.push_back('\n');
            } else if (c == 't') {
                value.push_back('\t');
            } else {
                value.push_back(c);
            }
            escape = false;
            continue;
        }
        if (c == '\\') {
            escape = true;
            continue;
        }
        if (c == '"') {
            vocab.push_back(value);
            inString = false;
            continue;
        }
        value.push_back(c);
    }
    return vocab;
}

std::vector<std::string> parseVocabLines(const std::string& body) {
    std::vector<std::string> vocab;
    std::istringstream stream(body);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (!line.empty()) {
            vocab.push_back(line);
        }
    }
    return vocab;
}

std::vector<std::string> loadVocab() {
    const char* envPath = std::getenv("HIFIVE_OCR_VOCAB");
    std::vector<std::string> candidates;
    if (envPath && envPath[0] != '\0') {
        candidates.emplace_back(envPath);
    }
    candidates.emplace_back("/home/jetson/hifive/models/ocr_vocab.json");
    candidates.emplace_back("/home/jetson/hifive/models/ocr_metadata.json");
    candidates.emplace_back("/home/jetson/hifive/models/ocr_vocab.txt");

    for (const auto& path : candidates) {
        std::ifstream file(path, std::ios::binary);
        if (!file) {
            continue;
        }
        std::ostringstream ss;
        ss << file.rdbuf();
        const std::string body = ss.str();
        std::vector<std::string> vocab = parseVocabJson(body);
        if (vocab.empty()) {
            vocab = parseVocabLines(body);
        }
        if (!vocab.empty()) {
            vocab.insert(vocab.begin(), "");
            return vocab;
        }
    }
    return std::vector<std::string>{""};
}

const std::vector<std::string>& vocab() {
    static const std::vector<std::string> values = loadVocab();
    return values;
}

float classProbability(const float* timestep, int classes, int index) {
    float maxValue = timestep[0];
    for (int i = 1; i < classes; ++i) {
        maxValue = std::max(maxValue, timestep[i]);
    }
    if (maxValue >= 0.0F && maxValue <= 1.0F) {
        return timestep[index];
    }
    double denom = 0.0;
    for (int i = 0; i < classes; ++i) {
        denom += std::exp(static_cast<double>(timestep[i] - maxValue));
    }
    return static_cast<float>(std::exp(static_cast<double>(timestep[index] - maxValue)) / std::max(denom, 1e-12));
}

}  // namespace

extern "C" bool NvDsInferParseCustomYoloPlate(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList) {
    objectList.clear();
    if (parseSplitNms(outputLayersInfo, networkInfo, detectionParams, objectList)) {
        return true;
    }
    for (const auto& layer : outputLayersInfo) {
        if (parsePackedRows(layer, networkInfo, detectionParams, objectList)) {
            return true;
        }
        if (parseTransposedRows(layer, networkInfo, detectionParams, objectList)) {
            return true;
        }
    }
    return true;
}

extern "C" bool NvDsInferParseCustomCrnnPlate(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const&,
    float classifierThreshold,
    std::vector<NvDsInferAttribute>& attrList,
    std::string& attrString) {
    attrList.clear();
    attrString.clear();
    if (outputLayersInfo.empty()) {
        return false;
    }

    const NvDsInferLayerInfo& layer = outputLayersInfo[0];
    const auto& dims = layer.inferDims;
    if (dims.numDims <= 0) {
        return false;
    }
    const int classes = dims.d[dims.numDims - 1];
    if (classes <= 1) {
        return false;
    }
    const int timesteps = static_cast<int>(volume(dims) / static_cast<size_t>(classes));
    const float* probs = asFloat(layer);
    const auto& vocabValues = vocab();

    int previous = kBlankIndex;
    float confidenceSum = 0.0F;
    int emitted = 0;
    std::string text;
    for (int t = 0; t < timesteps; ++t) {
        const float* step = probs + t * classes;
        int bestIndex = 0;
        for (int c = 1; c < classes; ++c) {
            if (step[c] > step[bestIndex]) {
                bestIndex = c;
            }
        }
        const float prob = classProbability(step, classes, bestIndex);
        if (bestIndex != previous && bestIndex != kBlankIndex) {
            if (bestIndex >= 0 && bestIndex < static_cast<int>(vocabValues.size())) {
                text += vocabValues[bestIndex];
            } else {
                text += "?";
            }
            confidenceSum += prob;
            ++emitted;
        }
        previous = bestIndex;
    }

    const float confidence = emitted > 0 ? confidenceSum / static_cast<float>(emitted) : 0.0F;
    if (confidence < classifierThreshold || text.empty()) {
        return true;
    }

    NvDsInferAttribute attr{};
    attr.attributeIndex = 0;
    attr.attributeValue = 0;
    attr.attributeConfidence = confidence;
    attr.attributeLabel = strdup(text.c_str());
    attrList.push_back(attr);
    attrString = text;
    return true;
}

CHECK_CUSTOM_PARSE_FUNC_PROTOTYPE(NvDsInferParseCustomYoloPlate);
CHECK_CUSTOM_CLASSIFIER_PARSE_FUNC_PROTOTYPE(NvDsInferParseCustomCrnnPlate);
