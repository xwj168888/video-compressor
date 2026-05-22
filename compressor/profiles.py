"""Compression profiles optimized for different use cases."""

PROFILES = {
    "ai": {
        "name": "AI 分析优化",
        "description": "适合发给 AI 分析，大幅压缩同时保留关键细节",
        "max_width": 1920,
        "max_height": 1080,
        "max_fps": 30,
        "codec": "hevc",
        "quality": 65,       # VideoToolbox quality (0-100)
        "crf": 28,           # software encoder CRF fallback
        "preset": "fast",
        "audio_bitrate": "64k",
    },
    "high": {
        "name": "极限压缩",
        "description": "最小体积，适合快速分享",
        "max_width": 1280,
        "max_height": 720,
        "max_fps": 15,
        "codec": "hevc",
        "quality": 50,
        "crf": 33,
        "preset": "fast",
        "audio_bitrate": "48k",
    },
    "balanced": {
        "name": "均衡压缩",
        "description": "兼顾画质和体积",
        "max_width": 1920,
        "max_height": 1080,
        "max_fps": 30,
        "codec": "h264",
        "quality": 70,
        "crf": 23,
        "preset": "medium",
        "audio_bitrate": "96k",
    },
    "lossless_small": {
        "name": "接近无损",
        "description": "几乎看不出差别，但体积仍有所减小",
        "max_width": 0,      # keep original
        "max_height": 0,
        "max_fps": 0,        # keep original
        "codec": "hevc",
        "quality": 90,
        "crf": 18,
        "preset": "slow",
        "audio_bitrate": "128k",
    },
}


def get_profile(name: str) -> dict:
    """Get a named profile, or return 'ai' as default."""
    return PROFILES.get(name, PROFILES["ai"])
