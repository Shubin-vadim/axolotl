"""
CLI to run training on a model
"""
import logging
import warnings
from pathlib import Path
from typing import Union

import fire
import transformers
from accelerate import init_empty_weights
from colorama import Fore
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM

from axolotl.cli import (
    check_accelerate_default_config,
    check_user_token,
    load_cfg,
    load_datasets,
    load_rl_datasets,
    print_axolotl_text_art,
)
from axolotl.common.cli import PreprocessCliArgs
from axolotl.common.const import DEFAULT_DATASET_PREPARED_PATH
from axolotl.convert import ConverterToJsonl, CsvParser, FileWriter, JsonlSerializer
from axolotl.prompt_strategies.sharegpt import (
    register_chatml_template,
    register_llama3_template,
)
from axolotl.utils.trainer import disable_datasets_caching

LOG = logging.getLogger("axolotl.cli.preprocess")


def do_cli(config: Union[Path, str] = Path("examples/"), **kwargs):
    # pylint: disable=duplicate-code
    print_axolotl_text_art()
    parsed_cfg = load_cfg(config, **kwargs)
    parsed_cfg.is_preprocess = True
    check_accelerate_default_config()
    check_user_token()
    parser = transformers.HfArgumentParser((PreprocessCliArgs))
    parsed_cli_args, _ = parser.parse_args_into_dataclasses(
        return_remaining_strings=True
    )

    if parsed_cfg.chat_template == "chatml":
        if parsed_cfg.default_system_message:
            LOG.info(
                f"ChatML set. Adding default system message: {parsed_cfg.default_system_message}"
            )
            register_chatml_template(parsed_cfg.default_system_message)
        else:
            register_chatml_template()
    elif parsed_cfg.chat_template == "llama3":
        if parsed_cfg.default_system_message:
            LOG.info(
                f"LLaMA-3 set. Adding default system message: {parsed_cfg.default_system_message}"
            )
            register_llama3_template(parsed_cfg.default_system_message)
        else:
            register_llama3_template()

    if not parsed_cfg.dataset_prepared_path:
        msg = (
            Fore.RED
            + "preprocess CLI called without dataset_prepared_path set, "
            + f"using default path: {DEFAULT_DATASET_PREPARED_PATH}"
            + Fore.RESET
        )
        LOG.warning(msg)
        parsed_cfg.dataset_prepared_path = DEFAULT_DATASET_PREPARED_PATH

    with disable_datasets_caching():
        if parsed_cfg.rl:  # and parsed_cfg.rl != "orpo":
            load_rl_datasets(cfg=parsed_cfg, cli_args=parsed_cli_args)
        else:
            load_datasets(cfg=parsed_cfg, cli_args=parsed_cli_args)

    if parsed_cfg.dataset_prepared_path and parsed_cfg.datasets[0].path.endswith(
        ".csv"
    ):
        csv_file = parsed_cfg.datasets[0].path
        jsonl_file = (
            parsed_cfg.dataset_prepared_path
            + f"/{parsed_cfg.datasets[0].path.rsplit('.', 1)[0]}.jsonl"
        )
        LOG.info(f"Converting {csv_file} to {jsonl_file}...")

        converter = ConverterToJsonl(CsvParser(), FileWriter(), JsonlSerializer())
        converter.convert(csv_file, jsonl_file)
        parsed_cfg.dataset_file = jsonl_file  # Update config to use JSONL file path

    if parsed_cli_args.download:
        model_name = parsed_cfg.base_model
        with warnings.catch_warnings():
            # there are a bunch of useless UserWarnings about
            # "copying from a non-meta parameter in the checkpoint to a meta parameter in the current model"
            warnings.simplefilter("ignore")
            with init_empty_weights(include_buffers=True):
                # fmt: off
                try:
                    AutoModelForCausalLM.from_pretrained(
                        model_name, trust_remote_code=True
                    )
                except Exception as exc:  # pylint: disable=broad-exception-caught,unused-variable  # nosec B110  # noqa F841
                    pass
                # fmt: on

    LOG.info(
        Fore.GREEN
        + f"Success! Preprocessed data path: `dataset_prepared_path: {parsed_cfg.dataset_prepared_path}`"
        + Fore.RESET
    )


if __name__ == "__main__":
    load_dotenv()
    fire.Fire(do_cli)
