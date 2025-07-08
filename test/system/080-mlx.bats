#!/usr/bin/env bats

load helpers

MODEL=hf://mlx-community/SmolLM-135M-4bit

function skip_if_not_apple_silicon() {
    if ! is_apple_silicon; then
        skip "MLX runtime requires macOS with Apple Silicon"
    fi
}

function skip_if_no_mlx() {
    if ! python3 -c "import mlx_lm" 2>/dev/null; then
        skip "MLX runtime requires mlx-lm package to be installed"
    fi
}

@test "ramalama --runtime=mlx help shows MLX option" {
    run_ramalama --help
    is "$output" ".*mlx.*" "MLX should be listed as runtime option"
}

@test "ramalama --runtime=mlx info shows MLX runtime" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx info
    is "$output" ".*Runtime.*mlx.*" "info should show MLX runtime"
}

@test "ramalama --runtime=mlx automatically enables --nocontainer" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    # MLX should automatically set --nocontainer even when not specified
    run_ramalama --runtime=mlx --dryrun run ${MODEL}
    # Should succeed without error about container requirements
    is "$status" "0" "MLX should auto-enable --nocontainer"
    # Should not contain container runtime commands
    assert "$output" !~ "podman\|docker" "should not use container runtime"
}

@test "ramalama --runtime=mlx --container shows warning but works" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    # When user explicitly specifies --container with MLX, should warn but auto-switch to --nocontainer
    run_ramalama --runtime=mlx --container --dryrun run ${MODEL}
    is "$status" "0" "should work despite --container flag"
    assert "$output" !~ "podman\|docker" "should not use container runtime even with --container flag"
}

@test "ramalama --runtime=mlx --dryrun run shows server-client model" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx --dryrun run ${MODEL}
    is "$status" "0" "MLX run should work"
    # Should use python -m mlx_lm server for the server process
    is "$output" ".*mlx_lm.server.*" "should use MLX server command"
    is "$output" ".*--port.*" "should include port specification"
}

@test "ramalama --runtime=mlx --dryrun run with prompt shows server-client model" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    prompt="Hello, how are you?"
    run_ramalama --runtime=mlx --dryrun run ${MODEL} "$prompt"
    is "$status" "0" "MLX run with prompt should work"
    is "$output" ".*mlx_lm.server.*" "should use MLX server command"
    is "$output" ".*--port.*" "should include port specification"
}

@test "ramalama --runtime=mlx --dryrun run with temperature" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx --dryrun run --temp 0.5 ${MODEL} "test"
    is "$status" "0" "MLX run with temperature should work"
    is "$output" ".*--temp.*0.5.*" "should include temperature setting"
}

@test "ramalama --runtime=mlx --dryrun run with max tokens" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx --dryrun run --ctx-size 1024 ${MODEL} "test"
    is "$status" "0" "MLX run with ctx-size should work"
    is "$output" ".*--max-tokens.*1024.*" "should include max tokens setting"
}

@test "ramalama --runtime=mlx --dryrun serve shows MLX server command" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx --dryrun serve ${MODEL}
    is "$status" "0" "MLX serve should work"
    # Should use python -m mlx_lm.server
    is "$output" ".*mlx_lm.server.*" "should use MLX server command"
    is "$output" ".*--port.*8080.*" "should include default port"
}

@test "ramalama --runtime=mlx --dryrun serve with custom port" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx --dryrun serve --port 9090 ${MODEL}
    is "$status" "0" "MLX serve with custom port should work"
    is "$output" ".*--port.*9090.*" "should include custom port"
}

@test "ramalama --runtime=mlx --dryrun serve with host" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    run_ramalama --runtime=mlx --dryrun serve --host 127.0.0.1 ${MODEL}
    is "$status" "0" "MLX serve with custom host should work"
    is "$output" ".*--host.*127.0.0.1.*" "should include custom host"
}

@test "ramalama --runtime=mlx run fails on non-Apple Silicon" {
    if is_apple_silicon; then
        skip "This test only runs on non-Apple Silicon systems"
    fi
    
    run_ramalama 22 --runtime=mlx run ${MODEL}
    is "$output" ".*MLX.*Apple Silicon.*" "should show Apple Silicon requirement error"
}

@test "ramalama --runtime=mlx serve fails on non-Apple Silicon" {
    if is_apple_silicon; then
        skip "This test only runs on non-Apple Silicon systems"
    fi
    
    run_ramalama 22 --runtime=mlx serve ${MODEL}
    is "$output" ".*MLX.*Apple Silicon.*" "should show Apple Silicon requirement error"
}

@test "ramalama --runtime=mlx works with ollama model format" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    model="ollama://smollm:135m"
    run_ramalama --runtime=mlx --dryrun run "$model"
    is "$status" "0" "MLX should work with ollama model format"
    is "$output" ".*mlx_lm.server.*" "should use MLX server command"
}

@test "ramalama --runtime=mlx works with huggingface model format" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    model="huggingface://microsoft/DialoGPT-small"
    run_ramalama --runtime=mlx --dryrun run "$model"
    is "$status" "0" "MLX should work with huggingface model format"
    is "$output" ".*mlx_lm.server.*" "should use MLX server command"
}

@test "ramalama --runtime=mlx rejects --name option" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    # --name requires container mode, which MLX doesn't support
    run_ramalama 1 --runtime=mlx run --name test ${MODEL}
    is "$output" ".*--nocontainer.*--name.*conflict.*" "should show conflict error"
}

@test "ramalama --runtime=mlx rejects --privileged option" {
    skip_if_not_apple_silicon
    skip_if_no_mlx
    
    # --privileged requires container mode, which MLX doesn't support
    run_ramalama 1 --runtime=mlx run --privileged ${MODEL}
    is "$output" ".*--nocontainer.*--privileged.*conflict.*" "should show conflict error"
}
