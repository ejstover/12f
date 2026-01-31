#!/usr/bin/env python3
import json
import logging
import os
from datetime import datetime
from getpass import getpass
from typing import Iterable, List

from ciscoconfparse import CiscoConfParse
from netmiko import ConnectHandler

LOG_FILE = "config_fetcher.log"
DEFAULT_DEVICE_TYPE = "cisco_ios"


def setup_logging() -> None:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def parse_devices(raw_devices: str) -> List[str]:
    devices = [item.strip() for item in raw_devices.replace("\n", ",").split(",")]
    return [device for device in devices if device]


def sanitize_device_name(device: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in device)


def config_to_json(config_text: str) -> List[dict]:
    parse = CiscoConfParse(config_text.splitlines())
    return [
        {
            "text": obj.text,
            "children": [child.text for child in obj.all_children],
            "indent": obj.indent,
        }
        for obj in parse.ConfigObjs
    ]


def write_config_files(
    device_name: str,
    base_filename: str,
    config_text: str,
) -> None:
    folder = os.path.join(os.getcwd(), sanitize_device_name(device_name))
    os.makedirs(folder, exist_ok=True)

    raw_path = os.path.join(folder, f"{base_filename}.txt")
    json_path = os.path.join(folder, f"{base_filename}.json")

    with open(raw_path, "w", encoding="utf-8") as raw_file:
        raw_file.write(config_text)

    json_payload = config_to_json(config_text)
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_payload, json_file, indent=2)


def fetch_configs(
    device: str,
    username: str,
    password: str,
    device_type: str,
) -> None:
    print(f"Logging into {device}")
    logging.info("Logging into device %s", device)

    netmiko_config = {
        "device_type": device_type,
        "host": device,
        "username": username,
        "password": password,
    }

    connection = None
    try:
        connection = ConnectHandler(**netmiko_config)
        running_config = connection.send_command("show running-config")
        startup_config = connection.send_command("show startup-config")
    finally:
        if connection:
            try:
                connection.disconnect()
            except Exception:
                logging.exception("Failed to disconnect cleanly from %s", device)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    device_safe = sanitize_device_name(device)

    print("Writing running config to file")
    logging.info("Writing running config for %s", device)
    write_config_files(
        device,
        f"{timestamp}-{device_safe}-runningconfig",
        running_config,
    )

    print("Writing startup config to file")
    logging.info("Writing startup config for %s", device)
    write_config_files(
        device,
        f"{timestamp}-{device_safe}-startupconfig",
        startup_config,
    )


def main() -> None:
    setup_logging()

    try:
        raw_devices = input("Enter device hostnames/IPs (comma-separated): ").strip()
        if not raw_devices:
            print("No devices provided.")
            return

        devices = parse_devices(raw_devices)
        username = input("Username: ").strip()
        password = getpass("Password: ")
        device_type = input(
            f"Device type [{DEFAULT_DEVICE_TYPE}]: "
        ).strip() or DEFAULT_DEVICE_TYPE

        for device in devices:
            try:
                fetch_configs(device, username, password, device_type)
            except Exception as exc:
                print(f"Failed to retrieve configs from {device}: {exc}")
                logging.exception("Error retrieving configs from %s", device)
            else:
                print("Completed")
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        logging.exception("Unexpected failure in main execution")


if __name__ == "__main__":
    main()
