"""Pathfinder exception hierarchy."""


class PathfinderError(Exception):
    """Base error for expected Pathfinder failures."""


class ValidationError(PathfinderError):
    """Input data failed validation."""


class RuleValidationError(ValidationError):
    """Rule bundle failed validation."""


class NoFeasiblePathError(PathfinderError):
    """No roadmap path can satisfy current constraints."""


class UnknownStakeholderTypeError(ValidationError):
    """No questionnaire exists for the stakeholder type."""
