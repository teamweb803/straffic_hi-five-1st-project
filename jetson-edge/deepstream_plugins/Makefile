DS_ROOT ?= /opt/nvidia/deepstream/deepstream
CUDA_ROOT ?= /usr/local/cuda
CXX ?= g++

TARGET := libnvdsinfer_custom_hifive.so
SRC := hifive_ds_parsers.cpp

CXXFLAGS := -std=c++17 -Wall -Wextra -fPIC -O2
INCLUDES := -I$(DS_ROOT)/sources/includes -I$(CUDA_ROOT)/include
LDFLAGS := -shared
LIBS := -L$(CUDA_ROOT)/lib64 -lnvinfer

.PHONY: all clean install

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(LDFLAGS) -o $@ $< $(LIBS)

install: $(TARGET)
	mkdir -p /home/jetson/hifive/deepstream_plugins
	cp $(TARGET) /home/jetson/hifive/deepstream_plugins/$(TARGET)

clean:
	rm -f $(TARGET)
