% ramalama-info 1

## NAME
ramalama\-info - Display RamaLama configuration information


## SYNOPSIS
**ramalama info** [*options*]

## DESCRIPTION
Display configuration information in a json format.

## OPTIONS

#### **--help**, **-h**
show this help message and exit

## FIELDS

The `Engine` field indicates the OCI container engine used to launch the container in which to run the AI Model

The `Image` field indicates the default container image in which to run the AI Model

The `Runtime` field indicates which backend engine is used to execute the AI model:

    - `llama.cpp`: Uses the llama.cpp library for model execution
    - `vllm`: Uses the vLLM library for model execution

The `Store` field indicates the directory path where RamaLama stores its persistent data, including downloaded models, configuration files, and cached data. By default, this is located in the user's local share directory.

The `UseContainer` field indicates whether RamaLama will use containers or run the AI Models natively.

The `Version` field shows the RamaLama version.

## EXAMPLE

Info with no container engine
```
$ ramalama info
{
    "Engine": {
	"Name": ""
    },
    "Image": "quay.io/ramalama/ramalama",
    "Runtime": "llama.cpp",
    "Store": "/home/user/.local/share/ramalama",
    "UseContainer": false,
    "Version": "0.5.0"
}
```

Info with Podman engine
```
$ ramalama info
{
    "Engine": {
	"Info": {
	    "host": {
		"arch": "amd64",
		"buildahVersion": "1.38.0",
		"cgroupControllers": [
		    "cpu",
		    "io",
		    "memory",
		    "pids"
		],
		"cgroupManager": "systemd",
		"cgroupVersion": "v2",
		"conmon": {
		    "package": "conmon-2.1.12-3.fc41.x86_64",
		    "path": "/usr/bin/conmon",
		    "version": "conmon version 2.1.12, commit: "
		},
		"cpuUtilization": {
		    "idlePercent": 94.58,
		    "systemPercent": 1.45,
		    "userPercent": 3.97
		},
		"cpus": 32,
		"databaseBackend": "sqlite",
		"distribution": {
		    "distribution": "fedora",
		    "variant": "workstation",
		    "version": "41"
		},
		"eventLogger": "journald",
		"freeLocks": 2048,
		"hostname": "danslaptop",
		"idMappings": {
		    "gidmap": [
			{
			    "container_id": 0,
			    "host_id": 3267,
			    "size": 1
			},
			{
			    "container_id": 1,
			    "host_id": 524288,
			    "size": 65536
			}
		    ],
		    "uidmap": [
			{
			    "container_id": 0,
			    "host_id": 3267,
			    "size": 1
			},
			{
			    "container_id": 1,
			    "host_id": 524288,
			    "size": 65536
			}
		    ]
		},
		"kernel": "6.12.5-200.fc41.x86_64",
		"linkmode": "dynamic",
		"logDriver": "journald",
		"memFree": 19481915392,
		"memTotal": 134690271232,
		"networkBackend": "netavark",
		"networkBackendInfo": {
		    "backend": "netavark",
		    "dns": {
			"package": "aardvark-dns-1.13.1-1.fc41.x86_64",
			"path": "/usr/libexec/podman/aardvark-dns",
			"version": "aardvark-dns 1.13.1"
		    },
		    "package": "netavark-1.13.1-1.fc41.x86_64",
		    "path": "/usr/libexec/podman/netavark",
		    "version": "netavark 1.13.1"
		},
		"ociRuntime": {
		    "name": "crun",
		    "package": "crun-1.19.1-1.fc41.x86_64",
		    "path": "/usr/bin/crun",
		    "version": "crun version 1.19.1\ncommit: 3e32a70c93f5aa5fea69b50256cca7fd4aa23c80\nrundir: /run/user/3267/crun\nspec: 1.0.0\n+SYSTEMD +SELINUX +APPARMOR +CAP +SECCOMP +EBPF +CRIU +LIBKRUN +WASM:wasmedge +YAJL"
		},
		"os": "linux",
		"pasta": {
		    "executable": "/bin/pasta",
		    "package": "passt-0^20241211.g09478d5-1.fc41.x86_64",
		    "version": "pasta 0^20241211.g09478d5-1.fc41.x86_64\nCopyright Red Hat\nGNU General Public License, version 2 or later\n  <https://www.gnu.org/licenses/old-licenses/gpl-2.0.html>\nThis is free software: you are free to change and redistribute it.\nThere is NO WARRANTY, to the extent permitted by law.\n"
		},
		"remoteSocket": {
		    "exists": true,
		    "path": "/run/user/3267/podman/podman.sock"
		},
		"rootlessNetworkCmd": "pasta",
		"security": {
		    "apparmorEnabled": false,
		    "capabilities": "CAP_CHOWN,CAP_DAC_OVERRIDE,CAP_FOWNER,CAP_FSETID,CAP_KILL,CAP_NET_BIND_SERVICE,CAP_SETFCAP,CAP_SETGID,CAP_SETPCAP,CAP_SETUID,CAP_SYS_CHROOT",
		    "rootless": true,
		    "seccompEnabled": true,
		    "seccompProfilePath": "/usr/share/containers/seccomp.json",
		    "selinuxEnabled": true
		},
		"serviceIsRemote": false,
		"slirp4netns": {
		    "executable": "/bin/slirp4netns",
		    "package": "slirp4netns-1.3.1-1.fc41.x86_64",
		    "version": "slirp4netns version 1.3.1\ncommit: e5e368c4f5db6ae75c2fce786e31eef9da6bf236\nlibslirp: 4.8.0\nSLIRP_CONFIG_VERSION_MAX: 5\nlibseccomp: 2.5.5"
		},
		"swapFree": 8587309056,
		"swapTotal": 8589930496,
		"uptime": "299h 13m 36.00s (Approximately 12.46 days)",
		"variant": ""
	    },
	    "plugins": {
		"authorization": null,
		"log": [
		    "k8s-file",
		    "none",
		    "passthrough",
		    "journald"
		],
		"network": [
		    "bridge",
		    "macvlan",
		    "ipvlan"
		],
		"volume": [
		    "local"
		]
	    },
	    "registries": {
		"search": [
		    "registry.fedoraproject.org",
		    "registry.access.redhat.com",
		    "docker.io"
		]
	    },
	    "store": {
		"configFile": "/home/user/.config/containers/storage.conf",
		"containerStore": {
		    "number": 0,
		    "paused": 0,
		    "running": 0,
		    "stopped": 0
		},
		"graphDriverName": "overlay",
		"graphOptions": {},
		"graphRoot": "/home/user/.local/share/containers/storage",
		"graphRootAllocated": 2046687182848,
		"graphRootUsed": 203689807872,
		"graphStatus": {
		    "Backing Filesystem": "btrfs",
		    "Native Overlay Diff": "true",
		    "Supports d_type": "true",
		    "Supports shifting": "false",
		    "Supports volatile": "true",
		    "Using metacopy": "false"
		},
		"imageCopyTmpDir": "/var/tmp",
		"imageStore": {
		    "number": 87
		},
		"runRoot": "/run/user/3267/containers",
		"transientStore": false,
		"volumePath": "/home/user/.local/share/containers/storage/volumes"
	    },
	    "version": {
		"APIVersion": "5.3.1",
		"Built": 1732147200,
		"BuiltTime": "Wed Nov 20 19:00:00 2024",
		"GitCommit": "",
		"GoVersion": "go1.23.3",
		"Os": "linux",
		"OsArch": "linux/amd64",
		"Version": "5.3.1"
	    }
	},
	"Name": "podman"
    },
    "Image": "quay.io/ramalama/ramalama",
    "Runtime": "llama.cpp",
    "Store": "/home/user/.local/share/ramalama",
    "UseContainer": true,
    "Version": "0.5.0"
}
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Oct 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
