import network
import ntptime
import time
import gc
from machine import Pin, SPI, RTC, ADC
import st7789py as st7789
import dseg7b32 as your_font_small  # Smaller font module
import dseg64b as your_font_large   # Larger font module
import mini8 as your_font_micro   # Mini font module (8x8)
import mini16 as your_font_mini   # Mini font module (16x16)

# ============================
# Configuration Parameters
# ============================

# Time synchronization interval in hours
TIME_SYNC_INTERVAL_HOURS = 6  # Change '6' to your desired interval

# DST Settings for Greece
# DST starts at 3:00 AM on the last Sunday in March
# DST ends at 4:00 AM on the last Sunday in October

# ============================
# Helper Functions
# ============================

def init_display():
    """Initialize the ST7789 display."""
    return st7789.ST7789(
        SPI(1, baudrate=60000000, polarity=1, phase=1, sck=Pin(10), mosi=Pin(11)),
        240,  # Width
        320,  # Height
        reset=Pin(12, Pin.OUT),
        cs=Pin(9, Pin.OUT),
        dc=Pin(8, Pin.OUT),
        backlight=Pin(13, Pin.OUT),
        rotation=1  # Set to landscape
    )

def load_env_vars(filename='.env'):
    """Load environment variables from a .env file."""
    env_vars = {}
    try:
        with open(filename, 'r') as f:
            for line in f:
                # Remove comments and whitespace
                line = line.strip()
                if line and not line.startswith('#'):
                    key_value = line.split('=', 1)
                    if len(key_value) == 2:
                        key, value = key_value
                        env_vars[key.strip()] = value.strip()
        print("Environment variables loaded.")
    except OSError as e:
        print(f"Error loading {filename}: {e}")
    return env_vars

def display_message(display, text, color=st7789.WHITE, clear=False, font=your_font_mini):
    """
    Display a message on the screen using the specified font.
    If clear is True, the entire display is cleared.
    """
    if clear:
        display.fill(st7789.BLACK)  # Clear the entire display
    else:
        # Clear the entire display first
        display.fill(st7789.BLACK)
        # Use the specified font
        text_width = get_text_width(text, font)
        text_height = font.height()
        text_x = (display.width - text_width) // 2
        text_y = (display.height - text_height) // 2
        display_text(display, text, text_x, text_y, font, color)
        gc.collect()  # Perform garbage collection after drawing

def connect_wifi(display, ssid, password, timeout=10):
    """Connect to a Wi-Fi network with a timeout and display status messages."""
    if not ssid or not password:
        print("SSID or password is missing.")
        display_message(display, "SSID or password missing.", color=st7789.RED)
        time.sleep(3)
        display_message(display, "", clear=True)
        return False
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    attempt = 1
    while True:
        message = f"Connecting... Attempt {attempt}"
        print(message)
        display_message(display, message, color=st7789.WHITE)
        wlan.connect(ssid, password)
        start_time = time.time()
        while not wlan.isconnected():
            if time.time() - start_time > timeout:
                error_message = f"{ssid} failed!"
                print(error_message)
                display_message(display, error_message, color=st7789.RED)
                wlan.disconnect()
                time.sleep(30)  # Wait 30 seconds before retrying
                attempt += 1
                break  # Break the inner while loop to retry connection
            time.sleep(0.5)
        else:
            success_message = "Wi-Fi connected"
            print('Wi-Fi connected:', wlan.ifconfig())
            display_message(display, success_message, color=st7789.GREEN)
            time.sleep(2)  # Briefly display the success message
            display_message(display, "", clear=True)  # Clear the message
            return wlan  # Return the connected WLAN object

def day_of_week(year, month, day):
    """
    Calculate the day of the week using Zeller's Congruence.
    Returns:
        0 = Sunday, 1 = Monday, ..., 6 = Saturday
    """
    if month < 3:
        month += 12
        year -= 1
    q = day
    m = month
    K = year % 100
    J = year // 100
    h = (q + (13 * (m + 1)) // 5 + K + (K // 4) + (J // 4) + 5 * J) % 7
    day_week = (h + 6) % 7  # Convert to 0=Sunday, ..., 6=Saturday
    return day_week

def is_dst(year, month, day, hour):
    """
    Determine if Daylight Saving Time (DST) is in effect for Greece.
    Args:
        year (int): Current year
        month (int): Current month
        day (int): Current day
        hour (int): Current hour (24-hour format)
    Returns:
        bool: True if DST is active, False otherwise
    """
    # Find the last Sunday in March
    march_last_day = 31
    while march_last_day >= 25:
        dow = day_of_week(year, 3, march_last_day)
        if dow == 0:  # Sunday
            break
        march_last_day -= 1

    # Find the last Sunday in October
    october_last_day = 31
    while october_last_day >= 25:
        dow = day_of_week(year, 10, october_last_day)
        if dow == 0:  # Sunday
            break
        october_last_day -= 1

    # DST starts at 3:00 AM on the last Sunday in March
    if month > 3 and month < 10:
        return True
    elif month == 3:
        if day > march_last_day:
            return True
        elif day == march_last_day and hour >= 3:
            return True
        else:
            return False
    elif month == 10:
        if day < october_last_day:
            return True
        elif day == october_last_day and hour < 4:
            return True
        else:
            return False
    else:
        return False

def sync_time(display):
    """Synchronize the RTC with NTP server and display status messages."""
    message = "Synchronizing time with NTP..."
    print(message)
    display_message(display, message, color=st7789.WHITE)
    try:
        ntptime.settime()  # Sets RTC to UTC time
        success_message = "Time synchronized"
        print(success_message)
        display_message(display, success_message, color=st7789.GREEN)
        time.sleep(2)  # Briefly display the success message
        display_message(display, "", clear=True)  # Clear the message
    except Exception as e:
        error_message = "Failed to synchronize time"
        print(error_message, e)
        display_message(display, error_message, color=st7789.RED)
        time.sleep(2)
        display_message(display, "", clear=True)

def get_text_width(text, font):
    """Calculate the total width of the text based on the font."""
    width = 0
    for char in text:
        try:
            _, _, char_width = font.get_ch(char)
            width += char_width
        except KeyError:
            width += font.max_width()
    return width

def draw_glyph(display, x0, y0, glyph, width, height, color):
    """
    Draw a glyph on the display.
    Args:
        display: ST7789 display object
        x0 (int): X-coordinate of the glyph's top-left corner
        y0 (int): Y-coordinate of the glyph's top-left corner
        glyph: Glyph data (memoryview of bytes)
        width (int): Width of the glyph in pixels
        height (int): Height of the glyph in pixels
        color: Color to draw the glyph
    """
    byte_index = 0
    bits_per_row = ((width + 7) // 8) * 8  # Bits per row, rounded up to nearest byte
    bytes_per_row = bits_per_row // 8

    for y in range(height):
        x = 0
        while x < width:
            # Find the start of a sequence of 'on' pixels
            while x < width:
                byte = glyph[byte_index + (x // 8)]
                bit = 0x80 >> (x % 8)
                if byte & bit:
                    break
                x += 1
            x_start = x
            # Find the end of the sequence
            while x < width:
                byte = glyph[byte_index + (x // 8)]
                bit = 0x80 >> (x % 8)
                if not (byte & bit):
                    break
                x += 1
            # Draw the sequence as a horizontal line
            if x_start < x:
                display.hline(x0 + x_start, y0 + y, x - x_start, color)
            x += 1  # Move to the next pixel
        byte_index += bytes_per_row

def display_text(display, text, x, y, font, color):
    """
    Display text on the screen.
    Args:
        display: ST7789 display object
        text (str): Text to display
        x (int): X-coordinate to start drawing the text
        y (int): Y-coordinate to start drawing the text
        font: Font module to use
        color: Color of the text
    """
    for char in text:
        try:
            glyph, char_height, char_width = font.get_ch(char)
            draw_glyph(display, x, y, glyph, char_width, char_height, color)
            x += char_width
        except KeyError:
            x += font.max_width()

def display_time_digits(display, hour_text, minute_text, x_positions, y, font):
    """
    Display the hour and minute digits on the screen.
    """
    # Draw hour
    display_text(display, hour_text, x_positions['hour'], y, font, st7789.WHITE)
    # Draw minute
    display_text(display, minute_text, x_positions['minute'], y, font, st7789.WHITE)

def update_colon(display, x_positions, y, font, show_colon):
    """
    Draw or clear the colon at the specified position.
    """
    colon_width = get_text_width(":", font)
    colon_height = font.height()

    if show_colon:
        display_text(display, ":", x_positions['colon'], y, font, st7789.WHITE)
    else:
        # Clear colon area
        display.fill_rect(x_positions['colon'], y, colon_width, colon_height, st7789.BLACK)
    gc.collect()  # Perform garbage collection after drawing

# ============================
# Temperature Reading Functions
# ============================

# Initialize ADC on GPIO26 (ADC pin 4) for internal temperature sensor
sensor_temp = ADC(4)

def read_internal_temperature():
    """
    Read the internal temperature sensor and return the temperature in Celsius.
    """
    reading = sensor_temp.read_u16() * 3.3 / (65535)  # Read 16-bit ADC value
    temperature_c = 27 - (reading - 0.706)/0.001721
    return temperature_c

# ============================
# Main Function
# ============================

def main():
    """Main function to run the clock with temperature display."""
    gc.collect()  # Initial garbage collection
    env_vars = load_env_vars()
    
    # Retrieve Wi-Fi credentials from environment variables
    WIFI_SSID = env_vars.get('WIFI_SSID')
    WIFI_PASSWORD = env_vars.get('WIFI_PASSWORD')
    
    if not WIFI_SSID or not WIFI_PASSWORD:
        print("Wi-Fi credentials not found in .env file.")
        return  # Exit the main function if credentials are missing
    
    display = init_display()
    
    # Connect to Wi-Fi
    wlan = connect_wifi(display, WIFI_SSID, WIFI_PASSWORD)
    if not wlan:
        print("Unable to connect to Wi-Fi. Exiting.")
        return  # Exit if Wi-Fi connection fails
    
    sync_time(display)
    wlan.active(False)  # Turn off Wi-Fi to save power if not needed
    
    last_sync_time = time.time()
    sync_interval_seconds = TIME_SYNC_INTERVAL_HOURS * 3600
    
    last_hour = -1
    last_minute = -1
    dot_state = False  # For colon blinking
    
    # Set fonts
    time_font = your_font_large
    temp_font = your_font_small
    
    # Calculate positions for time display
    hour_text = '00'
    minute_text = '00'
    hour_width = get_text_width(hour_text, time_font)
    colon_width = get_text_width(":", time_font)
    minute_width = get_text_width(minute_text, time_font)
    total_time_width = hour_width + colon_width + minute_width
    
    # Calculate positions
    time_x = (display.width - total_time_width) // 2
    time_y = (display.height - time_font.height()) // 2 - time_font.height() // 2  # Slightly above center
    
    # Positions of hour, colon, minute
    positions = {
        'hour': time_x,
        'colon': time_x + hour_width,
        'minute': time_x + hour_width + colon_width
    }
    
    try:
        while True:
            # Get current UTC time from RTC
            current_time = time.localtime()
            year = current_time[0]
            month = current_time[1]
            day = current_time[2]
            hour = current_time[3]
            minute = current_time[4]
            second = current_time[5]
    
            # Assume standard timezone offset (UTC+2)
            timezone_offset_hours = 2
            timezone_offset_seconds = timezone_offset_hours * 3600
    
            # Calculate tentative local time (UTC + 2)
            adjusted_time_seconds = time.time() + timezone_offset_seconds
            adjusted_time = time.localtime(adjusted_time_seconds)
            local_year = adjusted_time[0]
            local_month = adjusted_time[1]
            local_day = adjusted_time[2]
            local_hour = adjusted_time[3]
            local_minute = adjusted_time[4]
            local_second = adjusted_time[5]
    
            # Check if DST is in effect based on tentative local time
            if is_dst(local_year, local_month, local_day, local_hour):
                timezone_offset_hours = 3  # EEST (UTC+3)
            else:
                timezone_offset_hours = 2  # EET (UTC+2)
            timezone_offset_seconds = timezone_offset_hours * 3600
    
            # Recalculate local time with correct timezone offset
            adjusted_time_seconds = time.time() + timezone_offset_seconds
            adjusted_time = time.localtime(adjusted_time_seconds)
            local_year = adjusted_time[0]
            local_month = adjusted_time[1]
            local_day = adjusted_time[2]
            local_hour = adjusted_time[3]
            local_minute = adjusted_time[4]
            local_second = adjusted_time[5]
    
            # Check if hour or minute has changed
            if local_hour != last_hour or local_minute != last_minute:
                last_hour = local_hour
                last_minute = local_minute
    
                # Format the hour and minute text
                hour_text = '{:02}'.format(local_hour)
                minute_text = '{:02}'.format(local_minute)
    
                # Clear the hour and minute areas
                display.fill_rect(positions['hour'], time_y, hour_width, time_font.height(), st7789.BLACK)
                display.fill_rect(positions['minute'], time_y, minute_width, time_font.height(), st7789.BLACK)
    
                # Draw the hour and minute digits
                display_time_digits(display, hour_text, minute_text, positions, time_y, time_font)
    
                # Read and display temperature
                temperature = read_internal_temperature()
                temp_text = '{:0.1f}C'.format(temperature)
                temp_width = get_text_width(temp_text, temp_font)
                temp_x = (display.width - temp_width) // 2
                temp_y = time_y + time_font.height() + 10  # 10 pixels below time
    
                # Clear and draw temperature
                display.fill_rect(temp_x, temp_y, temp_width, temp_font.height(), st7789.BLACK)
                display_text(display, temp_text, temp_x, temp_y, temp_font, st7789.WHITE)
                gc.collect()
    
            # Toggle the colon every second
            dot_state = not dot_state
            update_colon(display, positions, time_y, time_font, dot_state)
    
            # Resynchronize time if needed
            if time.time() - last_sync_time >= sync_interval_seconds:
                wlan.active(True)
                wlan = connect_wifi(display, WIFI_SSID, WIFI_PASSWORD)
                if wlan:
                    sync_time(display)
                    last_sync_time = time.time()
                    wlan.active(False)
                    # After reconnection, redraw the time and temperature
                    last_hour = -1  # Force update
                else:
                    print("Unable to reconnect to Wi-Fi.")
                    # Continue running without resync
                    wlan.active(False)
    
            # Sleep for 1 second
            time.sleep(1)
            gc.collect()  # Perform garbage collection during sleep
    
    except KeyboardInterrupt:
        # Handle script interruption
        print('Script interrupted by user.')
    except Exception as e:
        print(f"An error occurred: {e}")

# ============================
# Run the Main Function
# ============================

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")

