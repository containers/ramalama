#!/bin/bash

# List of models to generate Containerfiles for
declare -A models=(
  ["granite/3b"]="ibm-granite/granite-3b-code-instruct-GGUF granite-3b-code-instruct.Q4_K_M.gguf"
  ["mistral/7b"]="TheBloke/Mistral-7B-Instruct-v0.1-GGUF mistral-7b-instruct-v0.1.Q2_K.gguf"
)

# Function to create directory and Containerfile
generate_containerfile() {
  local model_dir="$(echo $1 | tr '[:upper:]' '[:lower:]')"
  local hf_repo=$2
  local model_file=$3

  mkdir -p "container-images/$model_dir"

  cat <<EOF > "container-images/$model_dir/Containerfile"
FROM podman-llm/podman-llm:41

RUN llama-cpp-main --hf-repo $hf_repo -m $model_file

ENTRYPOINT ["llama-cpp-main", "-m", "/$model_file", "--log-disable"]
CMD ["--instruct"]
EOF
}

# Iterate over the models and generate Containerfiles
for model_dir in "${!models[@]}"; do
  IFS=' ' read -r -a model_info <<< "${models[$model_dir]}"
  hf_repo=${model_info[0]}
  model_file=${model_info[1]}

  generate_containerfile "$model_dir" "$hf_repo" "$model_file"
done

echo "Containerfiles have been generated successfully."

