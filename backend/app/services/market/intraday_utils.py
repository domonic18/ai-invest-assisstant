"""分时缩略图公共工具：等距降采样。"""

INTRADAY_SAMPLE_POINTS = 60


def downsample(values: list[float], limit: int = INTRADAY_SAMPLE_POINTS) -> list[float]:
    """等距降采样（保留首尾点），供分时缩略图使用。"""
    if len(values) <= limit:
        return values
    step = (len(values) - 1) / (limit - 1)
    return [values[round(i * step)] for i in range(limit)]
