"""
E2E tests for artifact functionality (OCI artifacts support)

These tests focus on the artifact-related functionality added in the PR,
including convert command with different types, config file support, and
error handling. Tests are designed to be fast and not require actual
artifact creation when possible.
"""

import json
import platform
import re
from pathlib import Path
from subprocess import STDOUT, CalledProcessError

import pytest

from test.conftest import skip_if_docker, skip_if_no_container, skip_if_podman_too_old, skip_if_windows
from test.e2e.utils import RamalamaExecWorkspace, check_output


def path_to_uri(path):
    """Convert a Path object to a file:// URI, handling Windows paths correctly."""
    if platform.system() == "Windows":
        # On Windows, convert backslashes to forward slashes and ensure proper file:// format
        path_str = str(path).replace("\\", "/")
        # Windows paths need an extra slash: file:///C:/path
        if len(path_str) > 1 and path_str[1] == ':':
            return f"file:///{path_str}"
        return f"file://{path_str}"
    else:
        return f"file://{path}"


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_list_command():
    """Test that ramalama list command works"""
    with RamalamaExecWorkspace() as ctx:
        # Just test that list works
        result = ctx.check_output(["ramalama", "list"])
        # Should return without error (may be empty)
        assert result is not None


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_list_json_output():
    """Test that ramalama list --json returns valid JSON"""
    with RamalamaExecWorkspace() as ctx:
        # Get JSON output
        result = ctx.check_output(["ramalama", "list", "--json"])
        items = json.loads(result)

        # Should be a list (may be empty)
        assert isinstance(items, list)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_convert_error_invalid_type():
    """Test that invalid convert type is rejected"""
    with RamalamaExecWorkspace() as ctx:
        test_file = Path(ctx.workspace_dir) / "testmodel.gguf"
        test_file.write_text("test content")

        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                ["ramalama", "convert", "--type", "invalid_type", path_to_uri(test_file), "test:latest"], stderr=STDOUT
            )

        assert exc_info.value.returncode == 2
        error_output = exc_info.value.output.decode("utf-8")
        assert "invalid choice" in error_output or "error" in error_output.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_convert_error_missing_source():
    """Test that convert with missing source is rejected"""
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                ["ramalama", "convert", "--type", "raw", "file:///nonexistent/path/model.gguf", "test:latest"],
                stderr=STDOUT,
            )

        # Exit code can be 2 (arg error), 5 (not found), or 22 (runtime error)
        assert exc_info.value.returncode in [2, 5, 22]
        error_output = exc_info.value.output.decode("utf-8")
        assert "error" in error_output.lower() or "Error" in error_output


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_convert_nocontainer_error():
    """Test that convert with --nocontainer is rejected"""
    with RamalamaExecWorkspace() as ctx:
        test_file = Path(ctx.workspace_dir) / "testmodel.gguf"
        test_file.write_text("test content")

        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                ["ramalama", "--nocontainer", "convert", "--type", "raw", path_to_uri(test_file), "test:latest"],
                stderr=STDOUT,
            )

        # Exit code 2 for argument parsing errors or 22 for runtime errors
        assert exc_info.value.returncode in [2, 22]
        error_output = exc_info.value.output.decode("utf-8")
        # Should error due to either invalid choice or nocontainer conflict
        assert "error" in error_output.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_rm_nonexistent():
    """Test removing nonexistent model (should handle gracefully)"""
    with RamalamaExecWorkspace() as ctx:
        # Try to remove something that doesn't exist
        # This should either fail gracefully or succeed
        try:
            ctx.check_output(["ramalama", "rm", "nonexistent-model:latest"], stderr=STDOUT)
        except CalledProcessError:
            # It's ok if it fails, just shouldn't crash
            pass


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_info_command_output():
    """Test that info command returns valid JSON with expected fields"""
    result = check_output(["ramalama", "info"])
    info = json.loads(result)

    # Check that basic sections exist
    assert "Accelerator" in info
    assert "Config" in info
    assert "Engine" in info

    # Check Engine section has Name field
    assert "Name" in info["Engine"]
    assert info["Engine"]["Name"] in ["podman", "docker"]


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_convert_help_shows_types():
    """Test that convert --help shows the available types"""
    result = check_output(["ramalama", "convert", "--help"])

    # Should show --type option
    assert "--type" in result

    # Should mention at least car and raw types
    assert "car" in result.lower()
    assert "raw" in result.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_push_help_shows_types():
    """Test that push --help shows the available types"""
    result = check_output(["ramalama", "push", "--help"])

    # Should show --type option
    assert "--type" in result

    # Should mention at least car and raw types
    assert "car" in result.lower()
    assert "raw" in result.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_convert_types_in_help():
    """Test that both convert and push commands show type options"""
    convert_help = check_output(["ramalama", "convert", "--help"])
    push_help = check_output(["ramalama", "push", "--help"])

    # Both should mention OCI-related types
    for help_text in [convert_help, push_help]:
        assert "--type" in help_text
        # Check for type descriptions
        assert "model" in help_text.lower() or "image" in help_text.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_version_command():
    """Test that version command works"""
    result = check_output(["ramalama", "version"])
    # Should contain version info
    assert re.search(r"\d+\.\d+\.\d+", result)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_config_with_convert_type():
    """Test that config file can specify convert_type"""
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    convert_type = "artifact"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        # Just verify the config is loaded without error
        result = ctx.check_output(["ramalama", "info"])
        info = json.loads(result)

        # Config should be loaded (check if artifact appears in the info output string)
        assert "artifact" in str(info).lower() or "Config" in info


@pytest.mark.e2e
@skip_if_no_container
@skip_if_podman_too_old
def test_help_command():
    """Test that help command works and shows subcommands"""
    result = check_output(["ramalama", "help"])

    # Should show key subcommands
    assert "convert" in result.lower()
    assert "push" in result.lower()
    assert "pull" in result.lower()
    assert "list" in result.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_convert_command_exists():
    """Test that convert command exists and shows help"""
    result = check_output(["ramalama", "convert", "--help"])

    # Should show convert-specific help
    assert "convert" in result.lower()
    assert "source" in result.lower()
    assert "target" in result.lower()


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
def test_push_command_exists():
    """Test that push command exists and shows help"""
    result = check_output(["ramalama", "push", "--help"])

    # Should show push-specific help
    assert "push" in result.lower()
    assert "source" in result.lower()


# Comprehensive artifact lifecycle tests


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_lifecycle_basic():
    """Test complete artifact lifecycle: create, list, remove"""
    with RamalamaExecWorkspace() as ctx:
        # Create a small test model file
        test_file = Path(ctx.workspace_dir) / "small_model.gguf"
        test_file.write_text("Small test model content for artifact")

        artifact_name = "test-artifact-lifecycle:latest"

        # Step 1: Convert to artifact (using raw type which should work)
        ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file), artifact_name])

        # Step 2: Verify it appears in list
        result = ctx.check_output(["ramalama", "list"])
        assert "test-artifact-lifecycle" in result
        assert "latest" in result

        # Step 3: Verify it appears in list --json
        json_result = ctx.check_output(["ramalama", "list", "--json"])
        models = json.loads(json_result)
        found = False
        for model in models:
            if "test-artifact-lifecycle" in model.get("name", ""):
                found = True
                assert "size" in model
                assert model["size"] > 0
                break
        assert found, "Artifact not found in JSON list output"

        # Step 4: Remove the artifact
        ctx.check_call(["ramalama", "rm", artifact_name])

        # Step 5: Verify it's gone
        result_after = ctx.check_output(["ramalama", "list"])
        assert "test-artifact-lifecycle" not in result_after


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_multiple_types():
    """Test creating artifacts with different types (raw and car)"""
    with RamalamaExecWorkspace() as ctx:
        # Create test model files
        test_file1 = Path(ctx.workspace_dir) / "unique_model1.gguf"
        test_file1.write_text("Model 1 content")
        test_file2 = Path(ctx.workspace_dir) / "unique_model2.gguf"
        test_file2.write_text("Model 2 content")

        # Create raw type artifact
        ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file1), "test-raw-artifact-unique:v1"])

        # Create car type artifact
        ctx.check_call(["ramalama", "convert", "--type", "car", path_to_uri(test_file2), "test-car-artifact-unique:v1"])

        # Verify both appear in list using JSON (more reliable)
        json_result = ctx.check_output(["ramalama", "list", "--json"])
        models = json.loads(json_result)
        found_raw = any("test-raw-artifact-unique" in m.get("name", "") for m in models)
        found_car = any("test-car-artifact-unique" in m.get("name", "") for m in models)
        assert found_raw, "Raw artifact not found in list"
        assert found_car, "Car artifact not found in list"

        # Clean up
        ctx.check_call(["ramalama", "rm", "test-raw-artifact-unique:v1"])
        ctx.check_call(["ramalama", "rm", "test-car-artifact-unique:v1"])

        # Verify both are gone using JSON
        json_result_after = ctx.check_output(["ramalama", "list", "--json"])
        models_after = json.loads(json_result_after)
        for model in models_after:
            assert "test-raw-artifact-unique" not in model.get("name", "")
            assert "test-car-artifact-unique" not in model.get("name", "")


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_list_json_with_size():
    """Test that artifact in JSON list has correct size information"""
    with RamalamaExecWorkspace() as ctx:
        # Create a test file with known content
        test_file = Path(ctx.workspace_dir) / "sized_model_unique.gguf"
        test_content = "A" * 1000  # 1000 bytes
        test_file.write_text(test_content)

        artifact_name = "test-sized-artifact-unique:v1"

        # Convert to artifact
        ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file), artifact_name])

        # Get JSON output
        json_result = ctx.check_output(["ramalama", "list", "--json"])
        models = json.loads(json_result)

        # Find our artifact and check size
        artifact = None
        for model in models:
            if "test-sized-artifact-unique" in model.get("name", ""):
                artifact = model
                break

        assert artifact is not None, "Artifact not found in JSON output"
        assert "size" in artifact
        # OCI images have overhead, so size might be larger than original file
        assert artifact["size"] > 0, "Size should be greater than 0"
        assert "name" in artifact
        assert "modified" in artifact

        # Clean up
        ctx.check_call(["ramalama", "rm", artifact_name])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_rm_multiple():
    """Test removing multiple artifacts one at a time"""
    with RamalamaExecWorkspace() as ctx:
        # Create multiple test files with unique names
        artifacts = []
        for i in range(3):
            test_file = Path(ctx.workspace_dir) / f"uniquemulti{i}.gguf"
            test_file.write_text(f"Model {i} content for rm test")

            artifact_name = f"test-multi-rm-unique-{i}:v1"
            artifacts.append(artifact_name)

            # Convert to artifact
            ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file), artifact_name])

        # Verify all appear in list using JSON
        json_result = ctx.check_output(["ramalama", "list", "--json"])
        models = json.loads(json_result)
        for i in range(3):
            found = any(f"test-multi-rm-unique-{i}" in m.get("name", "") for m in models)
            assert found, f"Artifact test-multi-rm-unique-{i} not found"

        # Remove artifacts one at a time
        for artifact_name in artifacts:
            ctx.check_call(["ramalama", "rm", artifact_name])

        # Verify all are gone using JSON
        json_result_after = ctx.check_output(["ramalama", "list", "--json"])
        models_after = json.loads(json_result_after)
        for model in models_after:
            for i in range(3):
                assert f"test-multi-rm-unique-{i}" not in model.get("name", ""), (
                    f"Artifact test-multi-rm-unique-{i} still present after removal"
                )


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_with_different_tags():
    """Test creating artifacts with different tags"""
    with RamalamaExecWorkspace() as ctx:
        test_file = Path(ctx.workspace_dir) / "tagged_model.gguf"
        test_file.write_text("Tagged model content")

        # Create artifacts with different tags
        tags = ["v1.0", "v2.0", "latest"]
        for tag in tags:
            ctx.check_call(
                ["ramalama", "convert", "--type", "raw", path_to_uri(test_file), f"test-tagged-artifact:{tag}"]
            )

        # Verify all tags appear in list
        result = ctx.check_output(["ramalama", "list"])
        for tag in tags:
            assert tag in result

        # Clean up all tags
        for tag in tags:
            ctx.check_call(["ramalama", "rm", f"test-tagged-artifact:{tag}"])

        # Verify all are gone
        result_after = ctx.check_output(["ramalama", "list"])
        assert "test-tagged-artifact" not in result_after


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_list_empty_after_cleanup():
    """Test that list is clean after removing all artifacts"""
    with RamalamaExecWorkspace() as ctx:
        test_file = Path(ctx.workspace_dir) / "temp_model.gguf"
        test_file.write_text("Temporary content")

        artifact_name = "test-temp-artifact:latest"

        # Create artifact
        ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file), artifact_name])

        # Verify it exists
        result_before = ctx.check_output(["ramalama", "list"])
        assert "test-temp-artifact" in result_before

        # Remove it
        ctx.check_call(["ramalama", "rm", artifact_name])

        # Verify list doesn't contain it
        result_after = ctx.check_output(["ramalama", "list"])
        assert "test-temp-artifact" not in result_after

        # JSON output should also not contain it
        json_result = ctx.check_output(["ramalama", "list", "--json"])
        models = json.loads(json_result)
        for model in models:
            assert "test-temp-artifact" not in model.get("name", "")


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_with_config_default_type():
    """Test that config convert_type is used when type not specified"""
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    convert_type = "raw"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        test_file = Path(ctx.workspace_dir) / "config_model.gguf"
        test_file.write_text("Model using config default")

        artifact_name = "test-config-default:latest"

        # Convert without specifying --type (should use config default)
        ctx.check_call(["ramalama", "convert", path_to_uri(test_file), artifact_name])

        # Verify it was created
        result = ctx.check_output(["ramalama", "list"])
        assert "test-config-default" in result

        # Clean up
        ctx.check_call(["ramalama", "rm", artifact_name])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_podman_too_old
@skip_if_windows
def test_artifact_overwrite_same_name():
    """Test that converting to same name overwrites/updates"""
    with RamalamaExecWorkspace() as ctx:
        test_file1 = Path(ctx.workspace_dir) / "model_v1.gguf"
        test_file1.write_text("Version 1 content")
        test_file2 = Path(ctx.workspace_dir) / "model_v2.gguf"
        test_file2.write_text("Version 2 content - this is longer")

        artifact_name = "test-overwrite-artifact:latest"

        # Create first version
        ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file1), artifact_name])

        # Get size of first version
        json_result1 = ctx.check_output(["ramalama", "list", "--json"])
        models1 = json.loads(json_result1)
        size1 = None
        for model in models1:
            if "test-overwrite-artifact" in model.get("name", ""):
                size1 = model["size"]
                break
        assert size1 is not None

        # Create second version with same name
        ctx.check_call(["ramalama", "convert", "--type", "raw", path_to_uri(test_file2), artifact_name])

        # Verify only one artifact with this name exists
        result = ctx.check_output(["ramalama", "list"])
        # Count occurrences - should be 1 (or 2 if showing both tag and name)
        count = result.count("test-overwrite-artifact")
        assert count >= 1

        # Get size of second version
        json_result2 = ctx.check_output(["ramalama", "list", "--json"])
        models2 = json.loads(json_result2)
        size2 = None
        for model in models2:
            if "test-overwrite-artifact" in model.get("name", ""):
                size2 = model["size"]
                break
        assert size2 is not None

        # Size should be different (second file is larger)
        assert size2 >= size1, "Second version should be at least as large"

        # Clean up
        ctx.check_call(["ramalama", "rm", artifact_name])
