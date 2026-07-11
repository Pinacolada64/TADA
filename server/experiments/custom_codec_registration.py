import codecs


# Define your custom codec
class SimpleCodec(codecs.Codec):
    def encode(self, input, errors='strict'):
        # For simplicity, encoding is just the reverse.
        return input[::-1], len(input)

    def decode(self, input, errors='strict'):
        # Simple decoding: replace "hello" with "world"
        return input.replace("hello", "world"), len(input)


# Incremental Encoder/Decoder (Unused for simplicity)
class SimpleIncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, input, final=False):
        return input


class SimpleIncrementalDecoder(codecs.IncrementalDecoder):
    def decode(self, input, final=False):
        return input


# Stream Writer/Reader (Also unused for simplicity)
class SimpleStreamWriter(SimpleCodec, codecs.StreamWriter):
    pass


class SimpleStreamReader(SimpleCodec, codecs.StreamReader):
    pass


# Register the codec
def find_simple_codec(name):
    if name == "simple":
        return codecs.CodecInfo(
            name="simple",
            encode=SimpleCodec().encode,
            decode=SimpleCodec().decode,
            incrementalencoder=SimpleIncrementalEncoder,
            incrementaldecoder=SimpleIncrementalDecoder,
            streamwriter=SimpleStreamWriter,
            streamreader=SimpleStreamReader,
        )
    return None

if __name__ == '__main__':
    print("Registering custom codec...")
    # Register the custom codec
    codecs.register(find_simple_codec)

    # Example Usage:
    custom_encoded_string = "hello world"
    decoded_string = codecs.decode(custom_encoded_string, "simple")
    print(decoded_string)  # Output: world world
