# Makefile - Biên dịch mã nguồn eBPF/XDP cho AWS Linux
CLANG ?= clang
LLC   ?= llc
ARCH  := $(shell uname -m | sed 's/x86_64/x86/' | sed 's/aarch64/arm64/')

BPF_CFLAGS := -O2 -g -Wall -target bpf -D__TARGET_ARCH_$(ARCH) -I/usr/include -I/usr/include/$(shell uname -m)-linux-gnu

TARGET := xdp_packet_filter.o
SOURCE := xdp_packet_filter.c

all: $(TARGET)

$(TARGET): $(SOURCE)
	$(CLANG) $(BPF_CFLAGS) -c $(SOURCE) -o $(TARGET)
	@echo "=========================================================="
	@echo " Biên dịch thành công eBPF Bytecode: $(TARGET)"
	@echo " Sẵn sàng nạp vào card mạng ENA (eth0) bằng lệnh ip link"
	@echo "=========================================================="

clean:
	rm -f $(TARGET)
