CXX      = g++
CXXFLAGS = -O3 -Wall -Wextra -std=c++0x
LDFLAGS  = -lz
TARGET   = fastq_qc
SRC      = fastq_qc.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TARGET)

.PHONY: all clean
