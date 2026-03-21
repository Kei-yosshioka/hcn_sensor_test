import spidev
import lgpio
import time

# --- 設定エリア ---
PWR_PIN = 25       # 電源ONピン（物理22番）
CHIP_SELECT = 0    # SPI CE0
SENSITIVITY = 0.125 # 報告書より: 1ppmあたり0.125Vの変化

# GPIOの準備
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, PWR_PIN)
lgpio.gpio_write(h, PWR_PIN, 1) # 電源ON

# SPIの準備
spi = spidev.SpiDev()
spi.open(0, CHIP_SELECT)
spi.max_speed_hz = 1000000
spi.mode = 0b01

def read_ads1118():
    # AIN0-AIN1 差動モード, ±4.096Vレンジ
    config = [0x85, 0x83]
    resp = spi.xfer2(config + [0x00, 0x00])
    value = (resp[0] << 8) | resp[1]
    if value > 32767:
        value -= 65536
    return value

try:
    print("--- 起動シーケンス開始 ---")
    print("1. センサ安定化待ち (10秒)...")
    time.sleep(10) # 報告書のタイムチャートに基づき、本来はもっと長い方が安定します

    print("2. ゼロ点（ベースライン）を取得中 (5秒)...")
    samples = []
    for _ in range(20):
        samples.append(read_ads1118())
        time.sleep(0.25)
    zero_point = sum(samples) / len(samples)
    print(f"   調整完了。ゼロ点RAW値: {zero_point:.2f}")

    print("\n--- 測定開始 (Ctrl+C で終了) ---")
    while True:
        raw_val = read_ads1118()
        
        # あなたが作成したロジック：
        # ゼロ点から「どれだけ下がったか」を正の数として計算
        adjusted_val = (zero_point - raw_val)
        
        # 電圧変化量に換算
        diff_voltage = adjusted_val * (4.096 / 32768.0)
        
        # 濃度(ppm)に換算
        gas_ppm = diff_voltage / SENSITIVITY
        
        # 0未満にならないよう制限（ノイズ対策）
        display_ppm = max(0, gas_ppm)
        
        print(f"変化電圧: {diff_voltage:.4f} V | 推定濃度: {display_ppm:.2f} ppm")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n測定を終了します。")
    lgpio.gpio_write(h, PWR_PIN, 0) # 電源OFF
    spi.close()
    lgpio.gpiochip_close(h)
