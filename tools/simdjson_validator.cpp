// Minimal validation-only CLI for the MethodLab JSONTestSuite runner.
// Build from the engine tree against its simdjson.cpp: no benchmark timing here.
// Return 0 if parser accepts, 1 if parser rejects, 2 on I/O or operational error.
#include "simdjson.h"
#include <iostream>
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  auto doc = simdjson::padded_string::load(argv[1]);
  if (doc.error()) { std::cerr << "Could not load input\n"; return 2; }
  simdjson::dom::parser parser;
  auto parsed = parser.parse(doc.value());
  return parsed.error() == simdjson::SUCCESS ? 0 : 1;
}
