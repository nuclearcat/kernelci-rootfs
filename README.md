# KernelCI Rootfs Builder

A configuration-driven tool for building optimized root filesystem images for Linux kernel testing. This repository contains configurations and scripts for creating minimal, test-specific rootfs images using Debos (Debian-based) and Buildroot backends.

## Features

- **Multiple Test Configurations**: 18+ pre-configured rootfs variants for different testing frameworks
- **Multi-Architecture Support**: Build for amd64, arm64, armhf, armel, i386, mips64el, mipsel, and riscv
- **Docker-Based Builds**: No local dependencies - everything runs in containers
- **Optimized Images**: Minimal size with fast boot times for CI environments
- **Flexible Output Formats**: Support for tar.xz, cpio.gz, ext4.xz, and initrd formats

## Quick Start

### Prerequisites

- Docker installed and running
- Python 3.6+ 
- At least 4GB RAM and 10GB disk space for builds

### Building Your First Rootfs

```bash
# List available configurations
./kernelci_rootfs.py --list-configs

# Build a basic Debian Bookworm rootfs for amd64
./kernelci_rootfs.py --config bookworm --arch amd64

# Build with verbose output
./kernelci_rootfs.py --config bookworm --arch amd64 --verbose

# If Docker requires sudo
./kernelci_rootfs.py --config bookworm --arch amd64 --sudo
```

Output files will be created in `output/<architecture>/` directory.

## Available Configurations

### Base Configurations
- **bookworm**: Minimal Debian Bookworm base system
- **buildroot-baseline**: Buildroot-based minimal system

### Test-Specific Configurations
- **bookworm-igt**: Intel GPU Tools testing
- **bookworm-ltp**: Linux Test Project
- **bookworm-kselftest**: Kernel self-tests
- **bookworm-v4l2**: Video4Linux2 testing
- **bookworm-libcamera**: Camera subsystem testing
- **bookworm-tast**: ChromeOS Tast testing framework
- **bookworm-rt**: Real-time kernel testing
- **bookworm-cros-flash**: ChromeOS firmware flashing
- **bookworm-deqp-runner**: GPU conformance testing
- **bookworm-gst-fluster**: GStreamer codec testing
- **bookworm-blktest**: Block layer testing
- **bookworm-libhugetlbfs**: Huge pages testing
- **bookworm-fault-injection**: Kernel fault injection
- **bookworm-vdso**: VDSO testing
- **bookworm-cros-ec-tests**: ChromeOS EC testing
- **bookworm-gst-h26forge**: H.264/H.265 testing

## Command Line Usage

```bash
./kernelci_rootfs.py [OPTIONS]

Options:
  --config, -c CONFIG      Rootfs configuration name (required)
  --arch, -a ARCH         Target architecture (required)
  --config-dir DIR        Configuration directory (default: configs)
  --output-dir, -o DIR    Output directory (default: output)
  --docker-image, -d IMG  Docker image for Debos (default: godebos/debos)
  --list-configs          List all available configurations
  --verbose, -v           Enable verbose output
  --sudo                  Force using sudo for Docker commands
  --no-sudo              Never use sudo for Docker commands
  --extra-args ARGS       Extra arguments for build tools
```

## Architecture

### Configuration System

The build system uses a layered configuration approach:

1. **Main Config** (`configs/rootfs-configs.yaml`): Defines all rootfs variants
2. **Build Template** (`configs/debos/rootfs.yaml`): Debos recipe using configuration variables
3. **Overlays** (`configs/debos/overlays/`): Test-specific files and configurations
4. **Scripts** (`configs/debos/scripts/`): Installation scripts for test frameworks

### Directory Structure

```
kernelci-rootfs/
├── kernelci_rootfs.py          # Main build tool
├── configs/
│   ├── rootfs-configs.yaml     # Configuration definitions
│   └── debos/
│       ├── rootfs.yaml         # Debos build template
│       ├── overlays/           # Test-specific overlays
│       │   ├── baseline/       # Base system files
│       │   ├── igt/           # IGT test files
│       │   ├── ltp/           # LTP test files
│       │   └── ...
│       └── scripts/            # Installation scripts
│           ├── install-bootrr.sh
│           ├── debian-igt.sh
│           └── ...
└── output/                     # Build outputs (created automatically)
    ├── amd64/
    ├── arm64/
    └── ...
```

## Adding New Test Configurations

To add a new test rootfs configuration:

1. **Add to main config** (`configs/rootfs-configs.yaml`):
```yaml
my-new-test:
  rootfs_type: debos
  debian_release: bookworm
  arch_list:
    - amd64
    - arm64
  extra_packages:
    - my-test-package
  script: "scripts/my-test-setup.sh"
  test_overlay: "overlays/my-test"
```

2. **Create overlay directory** (if needed):
```bash
mkdir -p configs/debos/overlays/my-test
# Add test-specific files
```

3. **Create installation script** (if needed):
```bash
# Create configs/debos/scripts/my-test-setup.sh
# Add installation and setup commands
```

4. **Test the configuration**:
```bash
./kernelci_rootfs.py --config my-new-test --arch amd64
```

For verbose output:
```bash
./kernelci_rootfs.py --config my-new-test --arch amd64 --verbose
```

## Configuration Options

Each rootfs configuration supports these options:

- `rootfs_type`: Build system (debos/buildroot)
- `debian_release`: Debian version (bookworm, bullseye, etc.)
- `arch_list`: Supported architectures
- `extra_packages`: Additional packages to install
- `extra_packages_remove`: Packages to remove for size optimization
- `extra_firmware_packages`: Firmware packages
- `script`: Installation script to run
- `test_overlay`: Overlay directory to apply
- `imagesize`: Root filesystem size (default: 2GB)
- `debos_memory`: Memory limit for Debos (default: 4G)
- `cpu_count`: CPU limit for builds
- `scratchsize`: Scratch space size
- `crush_image_options`: Image compression options

## Docker Integration

The tool automatically handles Docker operations:

- **Auto-detection**: Detects if sudo is needed for Docker
- **Container Management**: Runs builds in isolated containers
- **Volume Mounting**: Mounts configs and output directories
- **KVM Support**: Uses hardware acceleration when available
- **Cleanup**: Automatically removes containers after builds
- **Ownership Fix**: Ensures output files are owned by current user (when using sudo)

## Output Formats

Built images are available in multiple formats:

- **Tarball** (`.tar.xz`): Complete filesystem archive
- **CPIO** (`.cpio.gz`): Initramfs format
- **Ext4** (`.ext4.xz`): Compressed filesystem image
- **Initrd**: Initial RAM disk format

## Tips and Best Practices

### Performance Optimization
- Use `--verbose` for debugging build issues
- Ensure `/dev/kvm` exists for hardware acceleration
- Allocate sufficient memory for large builds (8GB+ for complex configs)

### Troubleshooting
- Check Docker daemon is running: `docker version`
- Verify sufficient disk space in output directory
- Use `--sudo` if getting Docker permission errors
- Check build logs in verbose mode for specific errors

### CI/CD Integration
```bash
# Example CI build command
./kernelci_rootfs.py --config bookworm-igt --arch amd64 --sudo --verbose
```

## Contributing

When contributing new test configurations:

1. Follow naming convention: `bookworm-<testname>`
2. Minimize package installation for faster builds
3. Test on multiple architectures when possible
4. Document any special requirements
5. Keep overlay files minimal and focused

## License

LGPL-2.1 - See individual files for detailed license information.

## Support

For issues and feature requests, please use the project's issue tracker.

## Acknowledgements

This project is maintained by the KernelCI community.

Special thanks to all contributors for their efforts in improving the Linux kernel testing infrastructure.

First implementation of the KernelCI Rootfs Builder was developed by Guillaume Tucker as `kci_rootfs` in the `kernelci-core` repository. We gratefully acknowledge his foundational work and contributions to this project.

For more information, visit the [KernelCI website](https://kernelci.org).
