% ramalama-transcribe 1

## NAME
ramalama\-transcribe - transcribe audio to text

## SYNOPSIS
**ramalama transcribe** [*options*] *model* [*audio*]

## DESCRIPTION
Transcribe an audio file to text with the whisper.cpp runtime and print the
result to standard output.

The whisper.cpp runtime is not the default and has to be selected with the
global **--runtime whisper.cpp** option, which must appear before the
subcommand, or by setting **runtime = "whisper.cpp"** in **ramalama.conf(5)**.

The **model** argument must name a whisper.cpp model file, for example
**huggingface://ggerganov/whisper.cpp/ggml-base.en.bin**. Naming only the
repository (**huggingface://ggerganov/whisper.cpp**) does not work because
whisper.cpp needs a single model file.

Audio in **wav**, **mp3**, **flac** and **ogg** format is passed to whisper.cpp as
is. Whichever of these formats the container image's whisper.cpp build can
decode is accepted.

When **audio** is omitted or is **-**, the audio is read from standard input
and written to a temporary file first. Pipe WAV data when using standard input,
for example:

```
ffmpeg -i recording.mp3 -f wav - | ramalama --runtime whisper.cpp transcribe MODEL > transcript.txt
```

The temporary file is removed when the command finishes, whether it succeeds,
fails or is interrupted.

The global **--dryrun** and **--nocontainer** options go before the subcommand,
like **--runtime**. With **--nocontainer**, the **whisper-cli** binary must be
installed on the host.

The container image defaults to **ghcr.io/ggml-org/whisper.cpp:main** and is
selected for the detected GPU. Set **images.WHISPER** in **ramalama.conf(5)**
to override it for every GPU, or **images.WHISPER_\<GPU\>** to override it for one
GPU. The **--image** option overrides both.

## OPTIONS


[//]: # (BEGIN included file options/authfile.md)
#### **--authfile**=*path*
Path to the authentication file for OCI registries.

[//]: # (END   included file options/authfile.md)


[//]: # (BEGIN included file options/device.md)
#### **--device**
Add a host device to the container. Optional permissions parameter can
be used to specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

The device specification is passed directly to the underlying container engine. See documentation of the supported container engine for more information.

Pass '--device=none' to explicitly add no device to the container, e.g., for
running a CPU-only performance comparison.

[//]: # (END   included file options/device.md)


[//]: # (BEGIN included file options/engine-args.md)
#### **--engine-args**="*args*"
Add *args* to the **podman** or **docker** invocation (before the container image), after RamaLama-generated options and model bind mounts.
The option may be specified multiple times; each value is shell-split and all tokens are passed to the engine in order.
Use for extra **--mount** flags (for example multimodal projector files) or other engine-specific options. Shell-quoting rules match **--runtime-args**.

[//]: # (END   included file options/engine-args.md)


[//]: # (BEGIN included file options/env.md)
#### **--env**=

Set environment variables inside the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and sets the variable only if it is set on the host.


[//]: # (END   included file options/env.md)


[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)

#### **--image**=*image*
OCI container image to run whisper.cpp with.
See the description for the default image and the per-GPU configuration keys.


[//]: # (BEGIN included file options/keep-groups.md)
#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.

[//]: # (END   included file options/keep-groups.md)

#### **--language**, **-l**=*language*
Spoken language of the audio (default: **auto**).
Use **auto** to let whisper.cpp detect the language.


[//]: # (BEGIN included file options/name.md)
#### **--name**, **-n**
Name of the container to run the Model in.

[//]: # (END   included file options/name.md)


[//]: # (BEGIN included file options/network.md)
#### **--network**=*none*
set the network mode for the container

[//]: # (END   included file options/network.md)


[//]: # (BEGIN included file options/oci-runtime.md)
#### **--oci-runtime**

Override the default OCI runtime used to launch the container. Container
engines like Podman and Docker, have their own default oci runtime that they
use. Using this option RamaLama will override these defaults.

On Nvidia based GPU systems, RamaLama defaults to using the
`nvidia-container-runtime`. Use this option to override this selection.

[//]: # (END   included file options/oci-runtime.md)


[//]: # (BEGIN included file options/privileged.md)
#### **--privileged**
By default, RamaLama containers are unprivileged (=false) and cannot, for
example, modify parts of the operating system. This is because by de‐
fault a container is only allowed limited access to devices. A "privi‐
leged" container is given the same access to devices as the user launch‐
ing the container, with the exception of virtual consoles (/dev/tty\d+)
when running in systemd mode (--systemd=always).

A privileged container turns off the security features that isolate the
container from the host. Dropped Capabilities, limited devices, read-
only mount points, Apparmor/SELinux separation, and Seccomp filters are
all disabled. Due to the disabled security features, the privileged
field should almost never be set as containers can easily break out of
confinement.

Containers running in a user namespace (e.g., rootless containers) can‐
not have more privileges than the user that launched them.

[//]: # (END   included file options/privileged.md)


[//]: # (BEGIN included file options/pull.md)
#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

[//]: # (END   included file options/pull.md)

#### **--runtime-args**=*args*
Arguments to append to the whisper-cli invocation.

#### **--seed**=*seed*
Accepted for consistency with the other subcommands. It has no effect with whisper.cpp.


[//]: # (BEGIN included file options/selinux.md)
#### **--selinux**=*true*
Enable SELinux container separation (default: `true`)

[//]: # (END   included file options/selinux.md)

#### **--threads**, **-t**=*N*
Number of CPU threads to use.
When unset, whisper.cpp chooses the number of threads.


[//]: # (BEGIN included file options/tls-verify.md)
#### **--tls-verify**=*true*
Require HTTPS and verify certificates when contacting OCI registries

[//]: # (END   included file options/tls-verify.md)

#### **--translate**
Translate the audio to English instead of transcribing it in its original
language.

## EXAMPLES

Transcribe a WAV file to standard output:

```
ramalama --runtime whisper.cpp transcribe huggingface://ggerganov/whisper.cpp/ggml-base.en.bin recording.wav > transcript.txt
```

Transcribe audio piped on standard input:

```
cat recording.wav | ramalama --runtime whisper.cpp transcribe huggingface://ggerganov/whisper.cpp/ggml-base.en.bin
```

Translate French audio to English on the host:

```
ramalama --runtime whisper.cpp --nocontainer transcribe --translate --language fr "file://$PWD/ggml-base.bin" french.wav
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**, **[ramalama.conf(5)](ramalama.conf.5.md)**

## HISTORY
Oct 2026, Originally compiled for whisper.cpp speech-to-text support
