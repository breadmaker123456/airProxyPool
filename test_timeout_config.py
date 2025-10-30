#!/usr/bin/env python3
"""
Test script to verify glider timeout configuration is working correctly.
"""

import os
import sys


def test_default_values():
    """Test that default timeout values are loaded correctly."""
    from proxychain.config import Settings
    
    settings = Settings()
    
    print("Testing default timeout values...")
    assert settings.glider_dial_timeout == 10, f"Expected dial_timeout=10, got {settings.glider_dial_timeout}"
    assert settings.glider_relay_timeout == 30, f"Expected relay_timeout=30, got {settings.glider_relay_timeout}"
    assert settings.glider_check_timeout == 8, f"Expected check_timeout=8, got {settings.glider_check_timeout}"
    assert settings.glider_max_failures == 2, f"Expected max_failures=2, got {settings.glider_max_failures}"
    print("✓ Default values correct")


def test_env_override():
    """Test that environment variables can override default values."""
    # Set environment variables
    os.environ['GLIDER_DIAL_TIMEOUT'] = '15'
    os.environ['GLIDER_RELAY_TIMEOUT'] = '60'
    os.environ['GLIDER_CHECK_TIMEOUT'] = '10'
    os.environ['GLIDER_MAX_FAILURES'] = '3'
    
    # Force reimport to pick up new env vars
    import importlib
    import proxychain.config
    importlib.reload(proxychain.config)
    from proxychain.config import Settings
    
    settings = Settings()
    
    print("\nTesting environment variable overrides...")
    assert settings.glider_dial_timeout == 15, f"Expected dial_timeout=15, got {settings.glider_dial_timeout}"
    assert settings.glider_relay_timeout == 60, f"Expected relay_timeout=60, got {settings.glider_relay_timeout}"
    assert settings.glider_check_timeout == 10, f"Expected check_timeout=10, got {settings.glider_check_timeout}"
    assert settings.glider_max_failures == 3, f"Expected max_failures=3, got {settings.glider_max_failures}"
    print("✓ Environment variables correctly override defaults")
    
    # Clean up
    del os.environ['GLIDER_DIAL_TIMEOUT']
    del os.environ['GLIDER_RELAY_TIMEOUT']
    del os.environ['GLIDER_CHECK_TIMEOUT']
    del os.environ['GLIDER_MAX_FAILURES']


def test_config_generation():
    """Test that glider config is generated correctly with timeout settings."""
    from proxychain.config import Settings
    from proxychain.glider_manager import GliderManager
    from proxychain.models import ProxyEndpoint
    
    print("\nTesting glider config generation...")
    
    settings = Settings()
    manager = GliderManager(settings)
    
    endpoint = ProxyEndpoint(
        id="test:socks5",
        node_uid="test",
        protocol="socks5",
        host="0.0.0.0",
        port=25000,
        public_host="127.0.0.1"
    )
    
    backend_uri = "ss://aes-256-gcm:password@example.com:8388"
    config = manager._build_config(endpoint, backend_uri)
    
    # Check that all timeout settings are in the config
    assert "dialtimeout=10" in config, "dialtimeout not found in config"
    assert "relaytimeout=30" in config, "relaytimeout not found in config"
    assert "checktimeout=8" in config, "checktimeout not found in config"
    assert "maxfailures=2" in config, "maxfailures not found in config"
    assert f"forward={backend_uri}" in config, "forward not found in config"
    
    print("✓ Config generation includes all timeout settings")
    print("\nGenerated config:")
    print("-" * 60)
    print(config)
    print("-" * 60)


def test_zero_relay_timeout():
    """Test that relay timeout can be disabled by setting to 0."""
    os.environ['GLIDER_RELAY_TIMEOUT'] = '0'
    
    import importlib
    import proxychain.config
    importlib.reload(proxychain.config)
    from proxychain.config import Settings
    from proxychain.glider_manager import GliderManager
    from proxychain.models import ProxyEndpoint
    
    print("\nTesting relay timeout disabled (set to 0)...")
    
    settings = Settings()
    manager = GliderManager(settings)
    
    endpoint = ProxyEndpoint(
        id="test:http",
        node_uid="test",
        protocol="http",
        host="0.0.0.0",
        port=26000,
        public_host="127.0.0.1"
    )
    
    backend_uri = "ss://aes-256-gcm:password@example.com:8388"
    config = manager._build_config(endpoint, backend_uri)
    
    # relaytimeout should not be in config when set to 0
    assert "relaytimeout" not in config, "relaytimeout should not be in config when set to 0"
    
    print("✓ Relay timeout correctly omitted when set to 0")
    
    # Clean up
    del os.environ['GLIDER_RELAY_TIMEOUT']


def main():
    """Run all tests."""
    print("=" * 60)
    print("Glider Timeout Configuration Tests")
    print("=" * 60)
    
    try:
        test_default_values()
        test_env_override()
        test_config_generation()
        test_zero_relay_timeout()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
