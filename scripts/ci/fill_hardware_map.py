# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause

"""Script to generate hardware map used by twister based on userdev_conf file or connected DKs."""
import subprocess

import yaml
import argparse
import logging

from packaging import version

logging.basicConfig(level=logging.INFO)

MIN_PCA10056_REVISION = "2.0.0"

pca_to_board = {
    "PCA10056": "nrf52840dk_nrf52840",
    "PCA10100": "nrf52833dk_nrf52833",
    "PCA10112": "nrf21540dk_nrf52840",
    "PCA10059": "nrf52840dongle_nrf52840",
    "PCA10095": "nrf5340dk_nrf5340_cpuapp",
    "PCA20053": "thingy53_nrf5340_cpuapp",
}

family_to_pca = {
    "NRF52840": "PCA10056",
    "NRF52833": "PCA10100",
    "NRF21540": "PCA10112",
    "NRF52840DONGLE": "PCA10059",
    "NRF5340": "PCA10095",
    "THINGY53": "PCA20053",
}


def main(hardware_map_path: str, userdev_conf_path: str):
    """
    Generate HW map file for twister.

    :param hardware_map_path: Available HW generated by twister command:
                              --generate-hardware-map hardware-map.yaml --persistent-hardware-map
    :param userdev_conf_path: userdev_conf file describing installed HW or
                              AUTO key to generate hardware-map basis on connected HW
    :return:
    """
    logging.info("Generating hardware map...")
    if userdev_conf_path.upper() != "AUTO":
        with open(userdev_conf_path) as ud_file:
            userdev_conf = yaml.safe_load(ud_file)["devices"]

        for ud_entry in userdev_conf:
            if ud_entry.get("boards", None):
                # remove io_testers. We don't want to run tests on io_testers
                logging.info(f"remove io_tester {ud_entry}")
                userdev_conf.remove(ud_entry)
            elif ud_entry.get("pca", None) == "PCA10056" and version.parse(
                ud_entry.get("revision", "0.0.1")
            ) < version.parse(MIN_PCA10056_REVISION):
                # remove too old gravitons
                logging.info(f"remove {ud_entry} since is too old")
                userdev_conf.remove(ud_entry)

    with open(hardware_map_path) as hw_file:
        hardware_map = yaml.safe_load(hw_file)
    to_remove = []
    for hw_entry in hardware_map:
        hw_entry["runner"] = "nrfjprog"
        hw_entry["connected"] = True
        segger = hw_entry["id"].lstrip("0")
        matched_pcas = []
        if userdev_conf_path.upper() != "AUTO":
            matched_pcas = [
                ud_entry["pca"]
                for ud_entry in userdev_conf
                if str(ud_entry.get("segger")) == segger and "pca" in ud_entry
            ]
        else:
            # Read out device family
            out = subprocess.run(
                ["nrfjprog", "--deviceversion", "--snr", segger], capture_output=True)
            family_string = out.stdout.decode("utf-8").split("_")[0]
            matched_pcas = (
                [family_to_pca[family_string]
                 ] if out.returncode == 0 and family_string in family_to_pca else []
            )
        if matched_pcas:
            # recover DK
            logging.debug(
                "Call nrfjprog --recover to check if board is operable.")
            recover = subprocess.run(
                ["nrfjprog", "--recover", "--snr", segger], capture_output=True)
            if recover.returncode != 0:
                # it is OK to continue if recovery fail. This DK will not be taken to test
                logging.warning(
                    f"Not possible to recover {segger} board, remove from available boards.")
                continue
            try:
                hw_entry["platform"] = pca_to_board[matched_pcas[0]]
            except KeyError:
                logging.warning(
                    f"platform not known or not supported {segger}")
                to_remove.append(hw_entry)
                continue
            # Collect all entries for nRF53 DKs
            if "nrf5340dk_nrf5340_cpuapp" in hw_entry["platform"]:
                # If older nRF53 board (3 serial IFs), remove first and second serial interface
                if segger.startswith("9601"):
                    logging.info(
                        f"Remove first and second serial interface for old nRF53 board {segger}")
                    if hw_entry["serial"] and "-if00" in hw_entry["serial"]:
                        to_remove.append(hw_entry)
                    elif hw_entry["serial"] and "-if02" in hw_entry["serial"]:
                        to_remove.append(hw_entry)
                # If newer nRF53 board, remove only first serial interface
                elif segger.startswith("10500"):
                    logging.info(
                        f"Remove first serial interface for nRF53 board {segger}")
                    if "-if00" in hw_entry["serial"]:
                        to_remove.append(hw_entry)
                else:
                    logging.warning(
                        f"Unrecognized version of nRF53 board {segger}")
            elif "nrf52840dk_nrf52840" in hw_entry["platform"]:
                # If newer nRF52 board, remove first serial interface
                if segger.startswith("1050") and "-if02" in hw_entry["serial"]:
                    to_remove.append(hw_entry)
        else:
            # HW not known or not connected. Mark for removal
            to_remove.append(hw_entry)

    # remove unuseful HW
    for item in to_remove:
        hardware_map.remove(item)

    with open(f"{hardware_map_path}_filled", "w") as hw_file:
        yaml.dump(hardware_map, hw_file)
    logging.info(f"Final hardware_map content: {hardware_map}")
    logging.info("End")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to generate hardware map used by twister based on userdev_conf file or connected DKs."
    )

    parser.add_argument(
        "--userdev_conf_path",
        required=True,
        type=str,
        help="'userdev_conf file' describing installed HW or 'AUTO' to generate hardware-map basis on connected HW",
    )
    parser.add_argument(
        "--hardware_map_path",
        required=True,
        type=str,
        help="Available HW generated by twister command: --generate-hardware-map\
             hardware-map.yaml --persistent-hardware-map",
    )
    args = parser.parse_args()

    main(args.hardware_map_path, args.userdev_conf_path)
