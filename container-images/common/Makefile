CUDA_BACKEND = cu128
ROCM_BACKEND = rocm6.3
INTEL_BACKEND = xpu

PYTHON_VERSION = 3.13
PYTHON_VERSION_CUDA = 3.12

PYTHON_PLATFORM = x86_64-manylinux_2_40
PYTHON_PLATFORM_AARCH64 := $(subst x86_64,aarch64,$(PYTHON_PLATFORM))

INDEXES = pypi.org download.pytorch.org

rag-backends = cpu $(CUDA_BACKEND) $(ROCM_BACKEND) $(INTEL_BACKEND) cpu-aarch64 $(CUDA_BACKEND)-aarch64
requirements-files-combined = $(addsuffix .txt,$(rag-backends))
requirements-files-split = $(foreach index,$(INDEXES),$(addsuffix -$(index).txt,$(rag-backends)))

$(filter $(CUDA_BACKEND)%,$(requirements-files-combined)): PYTHON_VERSION = $(PYTHON_VERSION_CUDA)
$(filter %-aarch64.txt,$(requirements-files-combined)): PYTHON_PLATFORM = $(PYTHON_PLATFORM_AARCH64)

MIN_UV_VERSION = 0.9.5
UV_VERSION = $(shell uv --version | cut -d" " -f2 2> /dev/null)

.PHONY: check-uv
check-uv:
ifeq ($(UV_VERSION),)
	@echo "uv is not available"
	@exit 1
else
	@MIN_VER=$$(echo -e "$(MIN_UV_VERSION)\n$(UV_VERSION)" | sort --version-sort | head -n1); \
	if [ "$$MIN_VER" != "$(MIN_UV_VERSION)" ]; then \
	    echo "uv >= $(MIN_UV_VERSION) is required, $$MIN_VER available"; \
	    exit 1; \
	fi
endif

.PHONY: rag-requirements
rag-requirements: check-uv $(requirements-files-split) build.txt build-cuda.txt

$(requirements-files-combined): %.txt: requirements-rag.in
	uv -q pip compile \
	--python-version $(PYTHON_VERSION) \
	--python-platform $(PYTHON_PLATFORM) \
	--torch-backend $(firstword $(subst -, ,$*)) \
	--upgrade \
	--generate-hashes \
	--emit-index-annotation \
	-o $@ $<

define split_req_template =
$(addsuffix .txt,$(addprefix $(1)-,$(INDEXES))): $(1).txt split-reqs.awk
	awk -f $$(lastword $$^) $$<
endef

$(foreach backend,$(rag-backends),$(eval $(call split_req_template,$(backend))))

build-cuda.txt: PYTHON_VERSION = $(PYTHON_VERSION_CUDA)

build.txt build-cuda.txt: build%.txt: requirements-rag-build.in
	uv -q pip compile \
	--python-version $(PYTHON_VERSION) \
	--upgrade \
	--generate-hashes \
	--emit-index-annotation \
	-o $@ $<
