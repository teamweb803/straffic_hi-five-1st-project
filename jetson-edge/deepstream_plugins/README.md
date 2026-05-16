# HI-FIVE DeepStream Custom Parsers

Build on Jetson:

```bash
cd ~/hifive/app/deepstream_plugins
make clean
make
make install
```

Output:

```text
/home/jetson/hifive/deepstream_plugins/libnvdsinfer_custom_hifive.so
```

Functions:

- `NvDsInferParseCustomYoloPlate`
- `NvDsInferParseCustomCrnnPlate`

The OCR parser reads vocabulary from `HIFIVE_OCR_VOCAB` first, then falls back to:

- `/home/jetson/hifive/models/ocr_vocab.json`
- `/home/jetson/hifive/models/ocr_metadata.json`
- `/home/jetson/hifive/models/ocr_vocab.txt`
