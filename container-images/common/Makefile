CUDA_BACKEND = cu128
ROCM_BACKEND = rocm6.3
INTEL_BACKEND = xpu

PYTHON_VERSION = 3.13
CUDA_PYTHON_VERSION = 3.12

AARCH64_PLATFORM = aarch64-manylinux_2_28

rag-backends = cpu $(CUDA_BACKEND) $(ROCM_BACKEND) $(INTEL_BACKEND) cpu-aarch64 $(CUDA_BACKEND)-aarch64
requirements-files = $(foreach backend,$(rag-backends),requirements-rag-$(backend).txt)

$(filter requirements-rag-$(CUDA_BACKEND)%,$(requirements-files)): PYTHON_VERSION = $(CUDA_PYTHON_VERSION)

.PHONY: rag-requirements
rag-requirements: $(requirements-files)

$(requirements-files): requirements-rag-%.txt: requirements-rag.in
	uv -q pip compile \
	--python-version $(PYTHON_VERSION) \
	$(if $(findstring aarch64,$*),--python-platform $(AARCH64_PLATFORM)) \
	--torch-backend $(subst -aarch64,,$*) \
	--upgrade \
	--generate-hashes \
	--emit-index-annotation \
	-o $@ $<
