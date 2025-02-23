#!/usr/bin/env bats

load helpers

@test "ramalama list - basic output" {
    headings="NAME *MODIFIED *SIZE"

    run_ramalama pull ollama://tinyllama
    run_ramalama list
    is "${lines[0]}" "$headings" "header line"

    run_ramalama list --noheading
    assert "${lines[0]}" !~ "$headings" "header line should not be there"

    run_ramalama list -n
    assert "${lines[0]}" !~ "$headings" "header line should not be there"

    run_ramalama --quiet list
    assert "${lines[0]}" !~ "$headings" "header line should not be there"

    run_ramalama -q list
    assert "${lines[0]}" !~ "$headings" "header line should not be there"
}

@test "ramalama list - json" {
    # 'created': ramalama includes fractional seconds, ramalama-remote does not
    tests="
name              | test(\"^[a-z0-9A-Z:/]\\+\")
modified          | tostring | test(\"^[a-z0-9A-Z:/]\\+\")
size              | tostring | test(\"^[0-9]\\+\$\")
"

    run_ramalama pull ollama://tinyllama
    run_ramalama list --json

    while read field; do
	actual=$(echo "$output" | jq -r ".[0].$field")
	dprint "# actual=<$actual> expect=<true}>"
	is "$actual" "true" "jq .$field"
    done < <(parse_table "$tests")
}


@test "ramalama list - rm -a removes all models" {
    run_ramalama rm -a
    run_ramalama list --noheading
    is "$output" ""
}

@test "ramalama rm --ignore" {
    random_image_name=i_$(safename)
    run_ramalama 1 rm ${random_image_name}
    is "$output" "Error: removing ${random_image_name}: \[Errno 2\] No such file or directory:.*"
    run_ramalama rm --ignore ${random_image_name}
    is "$output" ""
}

# vim: filetype=sh
