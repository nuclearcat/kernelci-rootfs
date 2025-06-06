#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1
# Copyright (C) 2025 Collabora Ltd.
# Author: Denys Fedoryshchenko <denys.f@collabora.com>

import argparse
import json
import os
import subprocess
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any


class KernelCIRootfsBuilder:
    """Main class for building KernelCI rootfs images using Docker containers."""
    
    def __init__(self, config_dir: str = "configs", output_dir: str = "output",
                 docker_image: str = "godebos/debos", verbose: bool = False, use_sudo: bool = None):
        self.config_dir = Path(config_dir).absolute()
        self.output_dir = Path(output_dir).absolute()
        self.docker_image = docker_image
        self.verbose = verbose
        self.use_sudo = use_sudo if use_sudo is not None else self._detect_docker_sudo()
        self.configs = self._load_configs()
        
    def _load_configs(self) -> Dict[str, Any]:
        """Load rootfs configurations from YAML file."""
        config_file = self.config_dir / "rootfs-configs.yaml"
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
            
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
            # Extract the rootfs_configs section
            return data.get('rootfs_configs', {})
    
    def list_configs(self) -> List[str]:
        """List all available rootfs configurations."""
        return list(self.configs.keys())
    
    def get_config(self, config_name: str) -> Dict[str, Any]:
        """Get a specific rootfs configuration."""
        if config_name not in self.configs:
            raise ValueError(f"Unknown configuration: {config_name}")
        return self.configs[config_name]
    
    def _detect_docker_sudo(self) -> bool:
        """Detect if sudo is needed for Docker commands."""
        # First try without sudo
        try:
            result = subprocess.run(['docker', 'version'], 
                                  capture_output=True, 
                                  check=False)
            if result.returncode == 0:
                return False
        except FileNotFoundError:
            pass
        
        # Try with sudo
        try:
            result = subprocess.run(['sudo', 'docker', 'version'], 
                                  capture_output=True, 
                                  check=False)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass
            
        return False
    
    def _check_docker(self) -> None:
        """Check if Docker is available and running."""
        docker_cmd = ['sudo', 'docker'] if self.use_sudo else ['docker']
        try:
            result = subprocess.run(docker_cmd + ['version'], 
                                  capture_output=True, 
                                  text=True, 
                                  check=False)
            if result.returncode != 0:
                if self.verbose:
                    print(f"Docker check failed: {result.stderr}")
                if not self.use_sudo:
                    raise RuntimeError("Docker is not accessible. "
                                     "Try running with --sudo if Docker requires sudo.")
                else:
                    raise RuntimeError("Docker is not running or not accessible even with sudo. "
                                     "Make sure Docker is installed and the daemon is running.")
        except FileNotFoundError:
            raise RuntimeError("Docker command not found. Please install Docker first.")
    
    def build_debos(self, config_name: str, arch: str, extra_args: List[str] = None) -> int:
        """Build a rootfs using Debos in a Docker container."""
        self._check_docker()
        config = self.get_config(config_name)
        
        # Validate architecture
        if 'arch_list' in config and arch not in config['arch_list']:
            raise ValueError(f"Architecture {arch} not supported for {config_name}. "
                           f"Supported: {config['arch_list']}")
        
        # Ensure output directory exists with architecture subdirectory
        arch_output_dir = self.output_dir / arch
        arch_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare Debos variables
        debos_vars = {
            'architecture': arch,
            'suite': config.get('debian_release', 'bookworm'),
            'basename': config_name,  # Use config_name directly as basename
            'extra_packages': ' '.join(config.get('extra_packages', [])),
            'extra_packages_remove': ' '.join(config.get('extra_packages_remove', [])),
            'extra_firmware_packages': ' '.join(config.get('extra_firmware_packages', [])),
            'script': config.get('script', ''),
            'test_overlay': config.get('test_overlay', ''),
            'crush_image_options': config.get('crush_image_options', ''),
        }
        
        # Filter out empty values to avoid passing empty template variables
        debos_vars = {k: v for k, v in debos_vars.items() if v}
        
        # debos by default running in container
        debos_cmd = []
                
        # Add resource limits
        if 'cpu_count' in config:
            debos_cmd.extend(['--cpus', str(config['cpu_count'])])
        if 'debos_memory' in config:
            debos_cmd.extend(['--memory', config['debos_memory']])
        if 'scratchsize' in config:
            debos_cmd.extend(['--scratchsize', config['scratchsize']])
            
        # Add variables
        for key, value in debos_vars.items():
            debos_cmd.extend(['-t', f'{key}:{value}'])
        
        # Add extra arguments if provided
        if extra_args:
            debos_cmd.extend(extra_args)
        
        # recipe
        debos_cmd.append('/configs/debos/rootfs.yaml')

        # Build Docker command
        docker_cmd = ['sudo', 'docker'] if self.use_sudo else ['docker']
        docker_cmd.extend([
            'run', '--rm',
            '-v', f'{self.config_dir}:/configs:ro',
            '-v', f'{arch_output_dir}:/output',
            '-w', '/output',
        ])
        
        # Add KVM device if available (improves performance)
        if os.path.exists('/dev/kvm'):
            docker_cmd.extend(['--device', '/dev/kvm'])
            
        # Add Docker image and Debos command
        docker_cmd.append(self.docker_image)
        docker_cmd.extend(debos_cmd)
        
        # Print command if verbose
        if self.verbose:
            print(f"Running: {' '.join(docker_cmd)}")
            print(f"Output directory: {arch_output_dir}")
            
        # Execute the build
        try:
            # Use subprocess with proper handling
            process = subprocess.Popen(docker_cmd, 
                                     stdout=subprocess.PIPE if not self.verbose else None,
                                     stderr=subprocess.PIPE if not self.verbose else None,
                                     text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0 and not self.verbose:
                if stdout:
                    print(f"Build output:\n{stdout}")
                if stderr:
                    print(f"Build errors:\n{stderr}", file=sys.stderr)
            
            # If build succeeded and we used sudo, chown output files to current user
            if process.returncode == 0 and self.use_sudo:
                uid = os.getuid()
                gid = os.getgid()
                chown_cmd = ['sudo', 'chown', '-R', f'{uid}:{gid}', str(arch_output_dir)]
                if self.verbose:
                    print(f"Changing ownership of output files: {' '.join(chown_cmd)}")
                subprocess.run(chown_cmd, check=True)
                    
            return process.returncode
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1
    
    def build_buildroot(self, config_name: str, arch: str) -> int:
        """Build a rootfs using Buildroot (placeholder for future implementation)."""
        config = self.get_config(config_name)
        
        if 'buildroot_branch' not in config:
            raise ValueError(f"Configuration {config_name} is not a Buildroot config")
            
        print(f"Buildroot builds not yet implemented for {config_name}")
        return 1


def main():
    """Main entry point for the kernelci_rootfs tool."""
    parser = argparse.ArgumentParser(
        description='Build KernelCI rootfs images using Docker containers'
    )
    
    parser.add_argument('--config', '-c',
                       help='Rootfs configuration name')
    parser.add_argument('--arch', '-a',
                       help='Target architecture (e.g., amd64, arm64, armhf)')
    parser.add_argument('--config-dir', default='configs',
                       help='Directory containing configuration files (default: configs)')
    parser.add_argument('--output-dir', '-o', default='output',
                       help='Output directory for built images (default: output)')
    parser.add_argument('--docker-image', '-d', default='godebos/debos',
                       help='Docker image to use for Debos builds (default: godebos/debos)')
    parser.add_argument('--list-configs', action='store_true',
                       help='List all available configurations and exit')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--sudo', action='store_true',
                       help='Use sudo for Docker commands')
    parser.add_argument('--no-sudo', action='store_true',
                       help='Do not use sudo for Docker commands (even if detected)')
    parser.add_argument('--extra-args', nargs=argparse.REMAINDER,
                       help='Extra arguments to pass to the build tool')
    
    args = parser.parse_args()
    
    # Determine sudo usage
    use_sudo = None
    if args.sudo:
        use_sudo = True
    elif args.no_sudo:
        use_sudo = False
    
    try:
        builder = KernelCIRootfsBuilder(
            config_dir=args.config_dir,
            output_dir=args.output_dir,
            docker_image=args.docker_image,
            verbose=args.verbose,
            use_sudo=use_sudo
        )
        
        if args.list_configs:
            print("Available configurations:")
            for config in sorted(builder.list_configs()):
                print(f"  {config}")
            return 0
            
        # For non-list operations, config and arch are required
        if not args.config or not args.arch:
            parser.error("--config and --arch are required for building")
            
        # Determine build type based on config
        config_data = builder.get_config(args.config)
        
        # Build the rootfs
        print(f"Building {args.config} for {args.arch}...")
        if builder.use_sudo and builder.verbose:
            print("Using sudo for Docker commands")
        
        if 'buildroot_branch' in config_data:
            return_code = builder.build_buildroot(args.config, args.arch)
        else:
            return_code = builder.build_debos(args.config, args.arch, args.extra_args)
            
        if return_code == 0:
            print(f"Build completed successfully. Output in: {args.output_dir}/{args.arch}")
        else:
            print(f"Build failed with return code: {return_code}", file=sys.stderr)
            
        return return_code
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())