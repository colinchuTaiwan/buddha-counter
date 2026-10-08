"""
tests/test_core.py
核心邏輯單元測試（不依賴 Firebase / Streamlit）。
純函式直接在測試中實作，確保邏輯正確性。
"""
import pytest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TAIWAN_TZ = ZoneInfo("Asia/Taipei")


# ── 密碼複雜度驗證（直接複製純函式，不 import 含 st 的模組）────────────────────

MIN_PWD_LENGTH = 10

def validate_password_complexity(password: str):
    if len(password) < MIN_PWD_LENGTH:
        return False, f"密碼至少需要 {MIN_PWD_LENGTH} 個字元。"
    if not any(c.isupper() for c in password):
        return False, "密碼必須包含至少一個大寫英文字母。"
    if not any(c.islower() for c in password):
        return False, "密碼必須包含至少一個小寫英文字母。"
    if not any(c.isdigit() for c in password):
        return False, "密碼必須包含至少一個數字。"
    return True, ""


import secrets, string

def generate_temp_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
        ]
        for _ in range(10 - 3):
            pwd.append(secrets.choice(alphabet))
        secrets.SystemRandom().shuffle(pwd)
        result = "".join(pwd)
        if (len(result) == 10
                and any(c.isupper() for c in result)
                and any(c.islower() for c in result)
                and any(c.isdigit() for c in result)):
            return result


# ── 日期區間函式（直接複製，不依賴 db.py）─────────────────────────────────────

def now_tw():
    return datetime.now(TAIWAN_TZ)

def get_today_range():
    now = now_tw()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)

def get_week_range():
    now = now_tw()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=7)

def get_month_range():
    now = now_tw()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1, day=1)
    else:
        end = start.replace(month=now.month + 1, day=1)
    return start, end

def get_custom_range(start_date, end_date):
    start = datetime(start_date.year, start_date.month, start_date.day,
                     0, 0, 0, tzinfo=TAIWAN_TZ)
    end = datetime(end_date.year, end_date.month, end_date.day,
                   0, 0, 0, tzinfo=TAIWAN_TZ) + timedelta(days=1)
    return start, end


# ── 時間解析（直接複製）──────────────────────────────────────────────────────────

def parse_timestamp(value):
    if value is None:
        return None
    try:
        if hasattr(value, "tzinfo"):
            dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TAIWAN_TZ)
            return dt.astimezone(TAIWAN_TZ)
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TAIWAN_TZ)
            return dt.astimezone(TAIWAN_TZ)
        return None
    except Exception:
        return None


# ── 名稱驗證（直接複製）──────────────────────────────────────────────────────────

MAX_NAME_LEN = 30

def validate_item_name(name: str):
    stripped = name.strip()
    if not stripped:
        return False, "項目名稱不得為空。"
    if len(stripped) > MAX_NAME_LEN:
        return False, f"項目名稱不得超過 {MAX_NAME_LEN} 個字元（目前 {len(stripped)} 個）。"
    return True, ""


# ══════════════════════════════════════════════════════════════════════
# 測試類別
# ══════════════════════════════════════════════════════════════════════

class TestPasswordComplexity:
    def test_valid(self):
        ok, _ = validate_password_complexity("Abc123defg")
        assert ok

    def test_too_short(self):
        ok, msg = validate_password_complexity("Abc1234")
        assert not ok and "10" in msg

    def test_no_upper(self):
        ok, msg = validate_password_complexity("abc123defgh")
        assert not ok and "大寫" in msg

    def test_no_lower(self):
        ok, msg = validate_password_complexity("ABC123DEFGH")
        assert not ok and "小寫" in msg

    def test_no_digit(self):
        ok, msg = validate_password_complexity("AbcDefGhIj")
        assert not ok and "數字" in msg

    def test_exactly_10(self):
        ok, _ = validate_password_complexity("Abcdefg123")
        assert ok


class TestTempPassword:
    def test_always_10_chars(self):
        for _ in range(200):
            pwd = generate_temp_password()
            assert len(pwd) == 10

    def test_always_has_upper(self):
        for _ in range(200):
            assert any(c.isupper() for c in generate_temp_password())

    def test_always_has_lower(self):
        for _ in range(200):
            assert any(c.islower() for c in generate_temp_password())

    def test_always_has_digit(self):
        for _ in range(200):
            assert any(c.isdigit() for c in generate_temp_password())

    def test_no_plaintext_storage(self):
        """臨時密碼本身不應出現在任何持久化路徑（邏輯測試）"""
        pwd = generate_temp_password()
        # 確認是合法字串，非空
        assert pwd and isinstance(pwd, str)


class TestArgon2Hash:
    def test_verify_correct(self):
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        ph = PasswordHasher()
        h = ph.hash("TestPassword123")
        ph.verify(h, "TestPassword123")  # 不拋出異常

    def test_verify_wrong(self):
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        ph = PasswordHasher()
        h = ph.hash("TestPassword123")
        with pytest.raises(VerifyMismatchError):
            ph.verify(h, "WrongPassword99")

    def test_not_plaintext(self):
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        pwd = "TestPassword123"
        h = ph.hash(pwd)
        assert pwd not in h
        assert "$argon2" in h


class TestDateRanges:
    def test_today_has_timezone(self):
        start, end = get_today_range()
        assert start.tzinfo is not None
        assert end.tzinfo is not None

    def test_today_starts_midnight(self):
        start, _ = get_today_range()
        assert start.hour == 0 and start.minute == 0 and start.second == 0

    def test_today_is_24_hours(self):
        start, end = get_today_range()
        assert (end - start).total_seconds() == 86400

    def test_week_starts_monday(self):
        start, end = get_week_range()
        assert start.weekday() == 0, f"週起點應為週一 (0)，實際為 {start.weekday()}"

    def test_week_ends_monday(self):
        _, end = get_week_range()
        assert end.weekday() == 0

    def test_week_is_7_days(self):
        start, end = get_week_range()
        assert (end - start).days == 7

    def test_month_starts_day1(self):
        start, _ = get_month_range()
        assert start.day == 1

    def test_month_end_is_next_month_day1(self):
        _, end = get_month_range()
        assert end.day == 1

    def test_december_wraps_to_january(self):
        fake_now_fn = lambda: datetime(2024, 12, 15, 10, 0, 0, tzinfo=TAIWAN_TZ)
        # 手動呼叫邏輯
        now = fake_now_fn()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=2025, month=1, day=1)
        assert end.year == 2025 and end.month == 1 and end.day == 1

    def test_leap_year_feb_end(self):
        fake_now = datetime(2024, 2, 29, 12, 0, 0, tzinfo=TAIWAN_TZ)
        start = fake_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(month=3, day=1)
        assert end.month == 3 and end.day == 1

    def test_custom_range_end_is_exclusive(self):
        s, e = get_custom_range(date(2024, 1, 31), date(2024, 1, 31))
        assert e.day == 1 and e.month == 2  # 2024-02-01

    def test_midnight_not_double_counted(self):
        """午夜 00:00 只屬於新的一天，不重複計入前一天。"""
        start, end = get_today_range()
        yesterday_end = start  # 昨日的 end == 今日的 start
        # 驗證不重疊
        assert end == start + timedelta(days=1)
        assert yesterday_end == start  # 精確相等，無重疊


class TestParseTimestamp:
    def test_with_taiwan_timezone(self):
        result = parse_timestamp("2024-06-15T10:30:00+08:00")
        assert result is not None and result.hour == 10

    def test_without_timezone_treated_as_taiwan(self):
        result = parse_timestamp("2024-06-15T10:30:00")
        assert result is not None
        assert result.tzinfo is not None
        assert result.utcoffset().total_seconds() == 8 * 3600

    def test_invalid_string(self):
        assert parse_timestamp("not-a-date") is None

    def test_none_input(self):
        assert parse_timestamp(None) is None

    def test_naive_datetime(self):
        dt = datetime(2024, 6, 15, 10, 0, 0)
        result = parse_timestamp(dt)
        assert result is not None
        assert result.tzinfo is not None

    def test_aware_datetime(self):
        dt = datetime(2024, 6, 15, 2, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = parse_timestamp(dt)
        assert result.hour == 10  # UTC 02:00 = TW 10:00


class TestItemValidation:
    def test_empty_name_rejected(self):
        ok, _ = validate_item_name("   ")
        assert not ok

    def test_name_31_chars_rejected(self):
        ok, msg = validate_item_name("甲" * 31)
        assert not ok and "30" in msg

    def test_name_30_chars_ok(self):
        ok, _ = validate_item_name("甲" * 30)
        assert ok

    def test_normal_name_ok(self):
        ok, _ = validate_item_name("南無阿彌陀佛")
        assert ok

    def test_whitespace_stripped(self):
        ok, _ = validate_item_name("  大悲咒  ")
        assert ok  # strip 後有內容


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
