class SimpleMathNode:
    CATEGORY = "Comfydex"
    FUNCTION = "run"
    RETURN_TYPES = ("INT",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "a": ("INT", {"default": 1}),
                "b": ("INT", {"default": 1}),
            }
        }

    def run(self, a, b):
        return (a + b,)


NODE_CLASS_MAPPINGS = {"SimpleMathNode": SimpleMathNode}
NODE_DISPLAY_NAME_MAPPINGS = {"SimpleMathNode": "SimpleMathNode"}
