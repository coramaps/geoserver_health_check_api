import json

class TestFeature:
    def __init__(self, data: dict):
        self.data = data
        # ...process data as needed...

    @classmethod
    def from_json(cls, json_str: str) -> "TestFeature":
        data = json.loads(json_str)
        return cls(data)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.data})"

# Example usage:
if __name__ == '__main__':
    # Replace json_str with your JSON string
    json_str = '{"type": "Feature", "stac_version": "1.0.0", "id": "S2A_32UND_20230201_0_L2A", "properties": { ...existing code... }}'
    feature = TestFeature.from_json(json_str)
    print(feature)
