class UserSimError(Exception):
    """网络、HTTP、解析等可恢复错误。消息里不得包含密钥（见 client.redact）。"""
