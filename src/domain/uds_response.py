"""Pure, bounded inspection of common UDS response headers and server timing."""

from dataclasses import dataclass


SERVICE_NAMES = {
    0x10: "会话控制", 0x11: "ECU 复位", 0x14: "清除 DTC", 0x19: "读取 DTC",
    0x22: "读取 DID", 0x23: "读取内存", 0x24: "读取标定", 0x27: "安全访问",
    0x28: "通信控制", 0x2A: "周期读取", 0x2C: "动态 DID", 0x2E: "写入 DID",
    0x2F: "IO 控制", 0x31: "例程控制", 0x34: "请求下载", 0x35: "请求上传",
    0x36: "传输数据", 0x37: "退出传输", 0x38: "文件传输", 0x3D: "写入内存",
    0x3E: "Tester Present", 0x85: "DTC 设置控制",
}
NRC_NAMES = {
    0x10: "GeneralReject", 0x11: "ServiceNotSupported", 0x12: "SubFunctionNotSupported",
    0x13: "IncorrectMessageLengthOrInvalidFormat", 0x14: "ResponseTooLong",
    0x21: "BusyRepeatRequest", 0x22: "ConditionsNotCorrect", 0x24: "RequestSequenceError",
    0x25: "NoResponseFromSubnetComponent", 0x26: "FailurePreventsExecutionOfRequestedAction",
    0x31: "RequestOutOfRange", 0x33: "SecurityAccessDenied", 0x35: "InvalidKey",
    0x36: "ExceedNumberOfAttempts", 0x37: "RequiredTimeDelayNotExpired",
    0x70: "UploadDownloadNotAccepted", 0x71: "TransferDataSuspended", 0x72: "GeneralProgrammingFailure",
    0x73: "WrongBlockSequenceCounter", 0x78: "ResponsePending",
    0x7E: "SubFunctionNotSupportedInActiveSession", 0x7F: "ServiceNotSupportedInActiveSession",
    0x81: "RpmTooHigh", 0x82: "RpmTooLow", 0x83: "EngineIsRunning", 0x84: "EngineIsNotRunning",
    0x85: "EngineRunTimeTooLow", 0x86: "TemperatureTooHigh", 0x87: "TemperatureTooLow",
    0x88: "VehicleSpeedTooHigh", 0x89: "VehicleSpeedTooLow", 0x8A: "ThrottlePedalTooHigh",
    0x8B: "ThrottlePedalTooLow", 0x8C: "TransmissionRangeNotInNeutral", 0x8D: "TransmissionRangeNotInGear",
    0x8F: "BrakeSwitchNotClosed", 0x90: "ShifterLeverNotInPark", 0x91: "TorqueConverterClutchLocked",
    0x92: "VoltageTooHigh", 0x93: "VoltageTooLow",
}
SESSION_NAMES = {1: "默认会话", 2: "编程会话", 3: "扩展会话", 4: "安全会话"}
STATUS_BITS = (
    "testFailed", "testFailedThisOperationCycle", "pendingDTC", "confirmedDTC",
    "testNotCompletedSinceLastClear", "testFailedSinceLastClear",
    "testNotCompletedThisOperationCycle", "warningIndicatorRequested",
)
MAX_DTC_PREVIEW_RECORDS = 16


@dataclass(frozen=True, slots=True)
class SessionTiming:
    session: int
    p2_ms: int
    p2_star_ms: int


@dataclass(frozen=True, slots=True)
class UdsResponse:
    service_id: int
    positive: bool
    nrc: int | None
    details: tuple[str, ...]
    timing: SessionTiming | None = None


def _require(data: bytes, length: int, message: str) -> None:
    if len(data) < length:
        raise ValueError(message)


def _dtc_record(data: bytes) -> str:
    code = data[:3].hex().upper()
    status = data[3]
    flags = ", ".join(f"{name}={int(bool(status & (1 << bit)))}" for bit, name in enumerate(STATUS_BITS))
    return f"DTC {code} / 状态 0x{status:02X}: {flags}"


def parse_uds_response(data: bytes) -> UdsResponse:
    if not isinstance(data, bytes) or not data:
        raise ValueError("UDS 响应为空；需要完整字节")
    if data[0] == 0x7F:
        _require(data, 3, "负响应缺少请求 SID 或 NRC；至少需要 3 字节")
        return UdsResponse(data[1], False, data[2],
                           (f"请求 SID 0x{data[1]:02X}", f"NRC 0x{data[2]:02X} {NRC_NAMES.get(data[2], '未知 NRC')}",
                            f"附加数据 {len(data) - 3} 字节"))
    service = data[0] - 0x40
    if service not in SERVICE_NAMES:
        raise ValueError(f"未知响应 SID 0x{data[0]:02X}；保留原始数据")
    details = [f"响应 SID 0x{data[0]:02X} / 请求 SID 0x{service:02X}"]
    timing = None
    if service == 0x10:
        if len(data) != 6:
            raise ValueError("会话时序按 ISO 14229 2013+ 布局需要 6 字节；当前数据不能生成有效时序")
        if data[1] not in SESSION_NAMES and not 0x40 <= data[1] <= 0x7E:
            raise ValueError(f"会话编号 0x{data[1]:02X} 为保留或不支持值；不更新有效时序")
        timing = SessionTiming(data[1], int.from_bytes(data[2:4], "big"), int.from_bytes(data[4:6], "big") * 10)
        details.extend((f"会话 0x{data[1]:02X} {SESSION_NAMES.get(data[1], '自定义会话')}",
                        f"ECU 声明 P2Server_max {timing.p2_ms} ms", f"ECU 声明 P2*Server_max {timing.p2_star_ms} ms"))
    elif service == 0x14:
        if len(data) != 1:
            raise ValueError("清除 DTC 正响应应为单字节 54")
        details.append("收到清除 DTC 正响应；未执行额外读码验证")
    elif service == 0x19:
        _require(data, 2, "DTC 响应缺少子功能")
        details.append(f"子功能 0x{data[1]:02X}")
        if data[1] == 0x02:
            _require(data, 3, "DTC 列表缺少状态支持掩码")
            if (len(data) - 3) % 4:
                raise ValueError("DTC 列表记录不完整；每项需要三字节码及一字节状态")
            count = (len(data) - 3) // 4
            details.extend((f"状态支持掩码 0x{data[2]:02X}", f"DTC 数量 {count}"))
            for index in range(min(count, MAX_DTC_PREVIEW_RECORDS)):
                start = 3 + index * 4
                details.append(_dtc_record(data[start:start + 4]))
            if count > MAX_DTC_PREVIEW_RECORDS:
                details.append(f"仅展示前 {MAX_DTC_PREVIEW_RECORDS} 项；完整记录保留于原始字节")
        elif data[1] in (0x04, 0x06):
            _require(data, 6, "DTC 快照/扩展响应缺少完整 DTC 与状态")
            details.extend((_dtc_record(data[2:6]), f"记录数据 {len(data) - 6} 字节；需项目编码定义"))
        else:
            details.append(f"子功能数据 {len(data) - 2} 字节；保留原始数据")
    elif service in (0x22, 0x2E, 0x2F):
        _require(data, 3, "DID 响应缺少两字节 DID")
        details.extend((f"DID {data[1:3].hex().upper()}", f"DID 后数据 {len(data) - 3} 字节；未按项目编码解释"))
    elif service == 0x31:
        _require(data, 4, "例程响应缺少子功能或两字节 RoutineID")
        details.extend((f"子功能 0x{data[1]:02X}", f"RoutineID {data[2:4].hex().upper()}", f"例程数据 {len(data) - 4} 字节"))
    else:
        minimum = {0x11: 2, 0x27: 2, 0x28: 2, 0x34: 2, 0x35: 2, 0x36: 2, 0x38: 2, 0x3E: 2, 0x85: 2}.get(service, 1)
        _require(data, minimum, "响应缺少必要的基础字段")
        details.append(f"服务数据 {len(data) - 1} 字节；仅识别服务，保留原始数据")
    return UdsResponse(service, True, None, tuple(details), timing)
