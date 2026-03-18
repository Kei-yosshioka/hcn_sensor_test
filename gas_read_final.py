import spidev
import lgpio
import time

# --- 設定エリア ---
PWR_PIN = 25        # 電源ONピン（物理22番ピン）
CHIP_SELECT = 0     # SPI CE0
SENSITIVITY = 0.125 # 報告書より: 1ppmあたり0.125Vの変化

# GPIOの準備
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, PWR_PIN)
lgpio.gpio_write(h, PWR_PIN, 1)  # 基板の電源をON

# SPIの準備
spi = spidev.SpiDev()
spi.open(0, CHIP_SELECT)
spi.max_speed_hz = 1000000
spi.mode = 0b01  # ADS1118はMode 1

def read_ads1118():
    # ADS1118設定: AIN0-AIN1 差動モード, ±4.096Vレンジ
    # 1カウントあたり 125uV (4.096 / 32768)
    config = [0x85, 0x83]
    resp = spi.xfer2(config + [0x00, 0x00])
    value = (resp[0] << 8) | resp[1]
    # 符号付き16bit整数に変換
    if value > 32767:
        value -= 65536
    return value

try:
    print("--- 起動シーケンス ---")
    print("1. センサ安定化待ち (10秒)...")
    time.sleep(10)

    print("2. ゼロ点（ベースライン）を取得中 (5秒)...")
    samples = []
    for _ in range(20):
        samples.append(read_ads1118())
        time.sleep(0.25)
    zero_point = sum(samples) / len(samples)
    print(f"   調整完了。基準RAW値: {zero_point:.2f}")

    print("\n--- 測定開始 (Ctrl+C で終了) ---")
    while True:
        raw_val = read_ads1118()
        
        # 【重要】基準からどれだけ電圧が「下がったか」を計算
        # (Vref - Vnow) の形にしてプラスの数値を得る
        adjusted_diff = (zero_point - raw_val)
        
        # 電圧の変化量に換算 (1カウント = 125uV)
        diff_voltage = adjusted_diff * (4.096 / 32768.0)
        
        # 濃度(ppm)に換算 (1ppm = 0.125V)
        gas_ppm = diff_voltage / SENSITIVITY
        
        # 0未満にならないよう制限（ノイズ対策）
        display_ppm = max(0, gas_ppm)
        
        print(f"変化電圧: {diff_voltage:.4f} V | 推定濃度: {display_ppm:.2f} ppm")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n測定を終了します。")
    lgpio.gpio_write(h, PWR_PIN, 0)  # 電源をOFF
    spi.close()
    lgpio.gpiochip_close(h)
