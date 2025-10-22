"""
视频模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from .base import Base


class Video(Base):
    """视频表 - 存储视频的元数据信息"""
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(128), nullable=False, unique=True, index=True)  # 视频ID，唯一
    platform = Column(String(32), index=True)  # 平台类型 (douyin/tiktok)
    
    # 基本信息
    desc = Column(Text)  # 视频描述
    text_extra = Column(Text)  # JSON格式的标签列表
    tag = Column(Text)  # JSON格式的分类标签
    type = Column(String(32))  # 视频类型
    
    # 视频属性
    height = Column(Integer)  # 视频高度
    width = Column(Integer)  # 视频宽度
    duration = Column(String(64))  # 视频时长
    uri = Column(String(128))  # 视频URI
    
    # 封面信息
    dynamic_cover = Column(Text)  # 动态封面URL
    static_cover = Column(Text)  # 静态封面URL
    
    # 用户信息
    uid = Column(String(128))
    sec_uid = Column(String(256))
    unique_id = Column(String(128))
    signature = Column(Text)  # 用户签名
    user_age = Column(Integer)
    nickname = Column(String(128))
    mark = Column(String(128))
    
    # 音乐信息
    music_author = Column(String(256))
    music_title = Column(String(512))
    music_url = Column(Text)
    
    # 统计数据
    digg_count = Column(Integer)
    comment_count = Column(Integer)
    collect_count = Column(Integer)
    share_count = Column(Integer)
    play_count = Column(Integer, default=-1)
    
    # 其他信息
    extra = Column(Text)  # 额外信息
    share_url = Column(Text)  # 分享URL
    collection_time = Column(String(64))  # 采集时间
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系：一个视频可以有多个任务
    tasks = relationship("Task", back_populates="video")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "video_id": self.video_id,
            "platform": self.platform,
            "desc": self.desc,
            "text_extra": self.text_extra,
            "tag": self.tag,
            "type": self.type,
            "height": self.height,
            "width": self.width,
            "duration": self.duration,
            "uri": self.uri,
            "dynamic_cover": self.dynamic_cover,
            "static_cover": self.static_cover,
            "uid": self.uid,
            "sec_uid": self.sec_uid,
            "unique_id": self.unique_id,
            "signature": self.signature,
            "user_age": self.user_age,
            "nickname": self.nickname,
            "mark": self.mark,
            "music_author": self.music_author,
            "music_title": self.music_title,
            "music_url": self.music_url,
            "digg_count": self.digg_count,
            "comment_count": self.comment_count,
            "collect_count": self.collect_count,
            "share_count": self.share_count,
            "play_count": self.play_count,
            "extra": self.extra,
            "share_url": self.share_url,
            "collection_time": self.collection_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

