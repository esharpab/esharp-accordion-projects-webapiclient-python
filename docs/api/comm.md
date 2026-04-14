# Comm &mdash; Raw Bus Transactions

Perform raw bus transactions over I2C, UART, SPI, and TCP sockets. All byte data is **hex-encoded** on the wire; the client handles encoding and decoding transparently so callers work with plain `bytes` objects.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `i2c(device_name, address, action, ...)` | `BusTransactionResponse` | I2C bus transaction. |
| `uart(device_name, action, ...)` | `BusTransactionResponse` | UART transaction. |
| `spi(device_name, action, ...)` | `BusTransactionResponse` | SPI transaction. |
| `socket(device_name, action, ...)` | `BusTransactionResponse` | TCP socket transaction. |

All methods return a `BusTransactionResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `device_name` | `str` | Device used for the transaction |
| `action` | `str` | Action performed |
| `received` | `bytes` | Received data (decoded from hex) |
| `number_of_bytes_received` | `int` | Number of bytes received |

---

## I2C

```python
client.comm.i2c(device_name, address, action,
                data_to_send=None, number_of_bytes_to_receive=0,
                max_retries=-1)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_name` | `str` | Device name as registered in the hardware manager |
| `address` | `int` | I2C 7-bit device address (0&ndash;127) |
| `action` | `BusActions` | `SEND`, `RECEIVE`, `SEND_RECEIVE`, or `SCAN` |
| `data_to_send` | `bytes` | Bytes to transmit (required for Send/SendReceive) |
| `number_of_bytes_to_receive` | `int` | Expected byte count for Receive/SendReceive |
| `max_retries` | `int` | Retry limit on NAK (`-1` = device default) |

### Examples

```python
from accordionq2.enums import BusActions

# Scan the bus for connected devices
resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x00,
                       action=BusActions.SCAN)
for addr in resp.received:
    print(f"Found device at 0x{addr:02X}")

# Write two bytes to address 0x50
client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                action=BusActions.SEND,
                data_to_send=bytes([0x00, 0x10]))

# Read 4 bytes from address 0x50
resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                       action=BusActions.RECEIVE,
                       number_of_bytes_to_receive=4)
print(resp.received.hex())  # e.g. "aabbccdd"

# Write-then-read (SendReceive)
resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                       action=BusActions.SEND_RECEIVE,
                       data_to_send=bytes([0x00]),
                       number_of_bytes_to_receive=2)
```

---

## UART

```python
client.comm.uart(device_name, action,
                 data_to_send=None, number_of_bytes_to_receive=0,
                 timeout_ms=1000)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_name` | `str` | Device name as registered in the hardware manager |
| `action` | `BusActions` | `SEND`, `RECEIVE`, `SEND_RECEIVE`, or `CLEAR_BUFFERS` |
| `data_to_send` | `bytes` | Bytes to transmit |
| `number_of_bytes_to_receive` | `int` | Expected receive count |
| `timeout_ms` | `int` | Receive timeout in milliseconds (default 1000) |

### Example

```python
# Send a SCPI query and read the response
resp = client.comm.uart("MyUartDevice",
                        action=BusActions.SEND_RECEIVE,
                        data_to_send=b"*IDN?\n",
                        number_of_bytes_to_receive=64,
                        timeout_ms=2000)
print(resp.received.decode("ascii"))
```

---

## SPI

```python
client.comm.spi(device_name, action,
                data_to_send=None, number_of_bytes_to_receive=0)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_name` | `str` | Device name as registered in the hardware manager |
| `action` | `BusActions` | `SEND`, `RECEIVE`, or `SEND_RECEIVE` |
| `data_to_send` | `bytes` | Bytes to clock out |
| `number_of_bytes_to_receive` | `int` | Expected receive count |

### Example

```python
# Full-duplex SPI transfer
resp = client.comm.spi("MySpiDevice",
                       action=BusActions.SEND_RECEIVE,
                       data_to_send=bytes([0xAA, 0xBB]),
                       number_of_bytes_to_receive=2)
print(resp.received.hex())
```

---

## Socket (TCP/IP)

```python
client.comm.socket(device_name, action,
                   host_name="", port=0,
                   data_to_send=None, number_of_bytes_to_receive=0,
                   termination_byte=0, use_termination_byte=False,
                   timeout_ms=1000)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_name` | `str` | Device name as registered in the hardware manager |
| `action` | `BusActions` | `SEND`, `RECEIVE`, or `SEND_RECEIVE` |
| `host_name` | `str` | Remote host name or IP address |
| `port` | `int` | Remote TCP port number |
| `data_to_send` | `bytes` | Bytes to send |
| `number_of_bytes_to_receive` | `int` | Expected receive count |
| `termination_byte` | `int` | Byte value used as a message boundary (0&ndash;255) |
| `use_termination_byte` | `bool` | Whether to use `termination_byte` as end-of-message marker |
| `timeout_ms` | `int` | Receive timeout in milliseconds |

### Example

```python
# Send a SCPI query over TCP
resp = client.comm.socket("MySocketDevice",
                          action=BusActions.SEND_RECEIVE,
                          host_name="192.168.1.10", port=5025,
                          data_to_send=b"*IDN?\n",
                          number_of_bytes_to_receive=64)
print(resp.received.decode("ascii"))
```
