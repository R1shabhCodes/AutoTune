"""
engine/optimizer/optuna_study.py
Optuna integration for AutoTune 2.0.
Maps adapter parameter declarations dynamically into an Optuna search space,
supporting TPE Bayesian Optimization, Random Search, custom constraints, and reproducible seeds.
"""
from typing import Dict, Any, List, Optional, Tuple, Callable
import optuna
from optuna.samplers import TPESampler, RandomSampler
from engine.integrations.schemas.protocol import ParameterSchema


# Suppress noisy default Optuna logs
optuna.logging.set_verbosity(optuna.logging.WARNING)


def build_optuna_search_space(
    trial: optuna.Trial,
    parameters: Dict[str, ParameterSchema],
    agent_suggested_bounds: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Dynamically generates candidate parameters for a trial based on the application's declared manifest,
    optionally refined by LLM agent hypothesis bounds.
    """
    candidate_config: Dict[str, Any] = {}

    for param_name, schema in parameters.items():
        p_type = schema.type.lower()
        bounds = agent_suggested_bounds.get(param_name, {}) if agent_suggested_bounds else {}

        # 1. Categorical parameters
        if p_type in ("categorical", "string") and schema.options:
            choices = bounds.get("options", schema.options)
            candidate_config[param_name] = trial.suggest_categorical(param_name, choices)

        # 2. Integer parameters
        elif p_type in ("integer", "int"):
            min_val = int(bounds.get("min", schema.min if schema.min is not None else 1))
            max_val = int(bounds.get("max", schema.max if schema.max is not None else 10))
            step = int(schema.step) if schema.step is not None and schema.step >= 1 else 1
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            candidate_config[param_name] = trial.suggest_int(param_name, min_val, max_val, step=step)

        # 3. Float parameters
        elif p_type in ("float", "number"):
            min_val = float(bounds.get("min", schema.min if schema.min is not None else 0.0))
            max_val = float(bounds.get("max", schema.max if schema.max is not None else 1.0))
            step = float(schema.step) if schema.step is not None else None
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            log_scale = bool(bounds.get("log", False)) and min_val > 0.0
            if log_scale:
                candidate_config[param_name] = trial.suggest_float(param_name, min_val, max_val, log=True)
            elif step:
                candidate_config[param_name] = trial.suggest_float(param_name, min_val, max_val, step=step)
            else:
                candidate_config[param_name] = trial.suggest_float(param_name, min_val, max_val)

        # 4. Boolean parameters
        elif p_type in ("boolean", "bool"):
            candidate_config[param_name] = trial.suggest_categorical(param_name, [True, False])

        # Default fallback to existing current or default value
        else:
            candidate_config[param_name] = schema.current if schema.current is not None else schema.default

    return candidate_config


def create_study(
    study_name: str,
    sampler_type: str = "tpe",
    seed: Optional[int] = 42,
    direction: Optional[str] = "maximize",
    directions: Optional[List[str]] = None,
    storage: Optional[str] = None
) -> optuna.Study:
    """
    Creates or resumes an Optuna study with TPE (Bayesian) or Random sampling.
    Supports persistent RDB/SQLite storage and both single-objective and multi-objective Pareto optimization.
    """
    if sampler_type.lower() == "random":
        sampler = RandomSampler(seed=seed)
    else:
        sampler = TPESampler(seed=seed)

    # Multi-objective Pareto vs single-objective
    if directions:
        return optuna.create_study(
            study_name=study_name,
            directions=directions,
            sampler=sampler,
            storage=storage,
            load_if_exists=True
        )

    return optuna.create_study(
        study_name=study_name,
        direction=direction or "maximize",
        sampler=sampler,
        storage=storage,
        load_if_exists=True
    )

