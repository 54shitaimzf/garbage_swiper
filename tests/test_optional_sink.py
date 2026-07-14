import unittest

from cloud.optional_sink import NullSink, TOPICS, create_sink


class OptionalSinkTests(unittest.TestCase):
    def test_default_sink_is_local_and_non_blocking(self):
        sink = create_sink(enabled=False)
        self.assertIsInstance(sink, NullSink)
        for topic in TOPICS:
            sink.publish(topic, {"ok": True})
        sink.close()

    def test_unknown_topic_is_rejected(self):
        with self.assertRaises(ValueError):
            NullSink().publish("robot/raw_cmd_vel", {})


if __name__ == "__main__":
    unittest.main()
