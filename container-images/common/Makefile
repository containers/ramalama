CUDA_BACKEND = cu128
ROCM_BACKEND = rocm6.3
INTEL_BACKEND = xpu

# Keep the versions below in sync with the python versions installed in build_tools.sh
PYTHON_VERSION = 3.14
CUDA_PYTHON_VERSION = 3.12

tools-backends = cpu $(CUDA_BACKEND) $(ROCM_BACKEND) $(INTEL_BACKEND) cpu-aarch64 $(CUDA_BACKEND)-aarch64
tools-requirements-files = $(foreach backend,$(tools-backends),requirements-tools-$(backend).txt)

$(filter requirements-tools-$(CUDA_BACKEND)%,$(tools-requirements-files)): PYTHON_VERSION = $(CUDA_PYTHON_VERSION)

.PHONY: tools-requirements
tools-requirements: $(tools-requirements-files)

$(tools-requirements-files): requirements-tools-%.txt: requirements-tools.in
	uv -q pip compile \
	--python-version $(PYTHON_VERSION) \
	--python-platform $(if $(findstring aarch64,$*),aarch64,x86_64)-manylinux_2_28 \
	--torch-backend $(subst -aarch64,,$*) \
	--upgrade \
	--generate-hashes \
	--emit-index-annotation \
	-o $@ $<

requirements-rag.txt: requirements-rag.in
	uv -q pip compile \
	--python-version $(PYTHON_VERSION) \
	--upgrade \
	--generate-hashes \
	--emit-index-annotation \
	-o $@ $<
