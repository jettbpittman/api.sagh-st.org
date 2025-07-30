import time
import threading

class SnowflakeIDGenerator:
    def __init__(self, id_type: int, grad_year: int = 0, epoch=1409547600000):
        """
        Snowflake ID Generator

        :param grad_year: Graduation Year of a Swimmer
        :param id_type: 1: Swimmer, 2: Meet, 3: Entry, 4: Team, 5: User, 6: Attendance
        :param epoch: A custom epoch to start counting from (in milliseconds).
        """
        self.year = grad_year
        self.id_type = id_type
        self.epoch = epoch
        self.sequence = 0
        self.last_timestamp = -1

        # Constants
        self.year_bits = 5
        self.id_type_bits = 5
        self.sequence_bits = 12

        self.max_year = -1 ^ (-1 << self.year_bits)
        self.max_id_type = -1 ^ (-1 << self.id_type_bits)
        self.max_sequence = -1 ^ (-1 << self.sequence_bits)

        self.year_shift = self.sequence_bits
        self.id_type_shift = self.year_bits + self.sequence_bits
        self.timestamp_shift = self.id_type_bits + self.sequence_bits + self.year_bits

        self.lock = threading.Lock()

        if self.year < 0 or self.year > self.max_year:
            raise ValueError(f"Grad Year must be between 0 and {self.max_year}")

        if self.id_type < 1 or self.id_type > 6:
            raise ValueError(f"ID Type must be between 0 and 6")

    def _current_timestamp(self):
        return int(time.time() * 1000)

    def _wait_for_next_millis(self, last_timestamp):
        timestamp = self._current_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._current_timestamp()
        return timestamp

    def generate_id(self):
        """
        Generate a new Snowflake ID.

        :return: A unique 64-bit ID.
        """
        with self.lock:
            timestamp = self._current_timestamp()

            if timestamp < self.last_timestamp:
                raise Exception("Clock moved backwards. Refusing to generate ID.")

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.max_sequence
                if self.sequence == 0:
                    timestamp = self._wait_for_next_millis(self.last_timestamp)
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            id_ = ((timestamp - self.epoch) << self.timestamp_shift) | \
                  (self.year << self.year_shift) | \
                  (self.id_type << self.id_type_shift) | \
                  self.sequence

            return id_

# Example usage
if __name__ == "__main__":
    generator = SnowflakeIDGenerator(grad_year=26, id_type=1).generate_id()

    print(generator)
