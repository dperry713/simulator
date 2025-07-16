import subprocess
import sys
import os


def install_requirements():
    """Install required packages"""
    requirements = [
        "customtkinter>=5.2.0",
        "obd>=0.7.1",
        "pyserial>=3.5"
    ]

    print("Installing OBD Monitor requirements...")

    for requirement in requirements:
        try:
            print(f"Installing {requirement}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", requirement])
            print(f"✓ {requirement} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install {requirement}: {e}")
            return False

    print("\n✓ All requirements installed successfully!")
    return True


if __name__ == "__main__":
    if install_requirements():
        print("\nYou can now run the OBD Monitor with:")
        print("python obd_monitor.py")
    else:
        print("\nSome packages failed to install. Please check the errors above.")
