#!/usr/bin/env bats

load helpers

@test "ramalama list - basic output" {
    headings="NAME *MODIFIED *SIZE"

    run_ramalama pull ollama://smollm:135m
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
    #FIXME jq version on mac does not like regex handling
    skip_if_darwin
    # 'created': ramalama includes fractional seconds, ramalama-remote does not
    tests="
name              | [a-z0-9A-Z:/]\\\+
modified          | [0-9]\\\+
size              | [0-9]\\\+
"

    run_ramalama pull ollama://tinyllama
    run_ramalama list --json

    while read field expect; do
	actual=$(echo "$output" | jq -r ".[0].$field")
	dprint "# actual=<$actual> expect=<$expect}>"
	is "$actual" "$expect" "jq .$field"
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
    is "$output" "Error: Model '${random_image_name}' not found.*"
    run_ramalama rm --ignore ${random_image_name}
    is "$output" ""
}

# vim: filetype=sh
