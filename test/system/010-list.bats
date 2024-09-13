#!/usr/bin/env bats

load helpers

@test "ramalama list - basic output" {
    headings="NAME *MODIFIED *SIZE"

    run_ramalama list
    is "${lines[0]}" "$headings" "header line"

    run_ramalama list --noheading
    assert "${lines[0]}" !~ "$headings" "header line should not be there"

    run_ramalama list -n
    assert "${lines[0]}" !~ "$headings" "header line should not be there"
}

@test "ramalama list - json" {
    # 'created': ramalama includes fractional seconds, ramalama-remote does not
    tests="
name              | [a-z0-9A-Z]\\\+
modified          | [0-9]\\\+
size              | [0-9]\\\+
"

    run_ramalama list --json

    while read field expect; do
        actual=$(echo "$output" | jq -r ".[0].$field")
        dprint "# actual=<$actual> expect=<$expect}>"
        is "$actual" "$expect" "jq .$field"
    done < <(parse_table "$tests")
}


#@test "ramalama list - rm -af removes all models" {
#FIXME    run_ramalama rm -af
#    is "$output" "Untagged: $IMAGE
#Untagged: $pauseImage
#Deleted: $imageID
#Deleted: $pauseID" "infra list gets removed as well"

#    run_ramalama list --noheading
#    is "$output" ""
#}

#FIXME
#@test "ramalama rm --ignore" {
#    random_image_name=i_$(safename)
#    run_ramalama 1 rm $random_image_name
#    is "$output" "Error: $random_image_name: image not known.*"
#    run_ramalama rm --ignore $random_image_name
#    is "$output" ""
#}

#FIXME
#@test "ramalama rm --force bogus" {
#    run_ramalama 1 rm bogus
#    is "$output" "Error: bogus: image not known" "Should print error"
#    run_ramalama rm --force bogus
#    is "$output" "" "Should print no output"

#    random_image_name=i_$(safename)
#    run_ramalama image tag $IMAGE $random_image_name
#    run_ramalama rm --force bogus $random_image_name
#    assert "$output" = "Untagged: localhost/$random_image_name:latest" "removed image"

#    run_ramalama list
#    assert "$output" !~ "$random_image_name" "image must be removed"
#}

# vim: filetype=sh
