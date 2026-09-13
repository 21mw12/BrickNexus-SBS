"""历史数据查询请求模型。"""

from .TimeSeriesQuerySchema import PointTimeRangeSchema, SampledPointTimeRangeSchema


class HistoryQuerySchema(SampledPointTimeRangeSchema):
    """多测点共享时间范围和采样数量的历史查询。"""

    pass


class RawHistoryQuerySchema(PointTimeRangeSchema):
    """真实测点全量查询，不包含采样数量。"""

    pass


class HistoryHeatmapQuerySchema(HistoryQuerySchema):
    """历史时间热力图和相关性矩阵查询。"""
