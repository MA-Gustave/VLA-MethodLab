// Standalone native split-stage benchmark for simdjson RVV-VLA.
// Measures actual internal stage1() / stage2() calls plus independent public DOM parse().
// Stage1 + Stage2 timings are NOT claimed to equal DOM timing.
#include "simdjson.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstdint>

static bool parse_ok(simdjson::dom::parser& p, const std::string& s) {
  return p.parse(s).error() == simdjson::SUCCESS;
}
static bool parse_ok(simdjson::dom::parser& p, const simdjson::padded_string& s) {
  return p.parse(s).error() == simdjson::SUCCESS;
}
static int select_backend(const std::string &backend) {
  const auto* chosen=simdjson::get_available_implementations()[backend];
  if (!chosen || !chosen->supported_by_runtime_system()) {
    std::cerr << "Unsupported backend: " << backend << "\n";
    return 3;
  }
  simdjson::get_active_implementation()=chosen;
  if (simdjson::get_active_implementation()->name()!=backend) return 4;
  return 0;
}
static int validate_file(simdjson::dom::parser& parser, const char *path, bool expected) {
  std::ifstream in(path);
  if (!in) { std::cerr << "Missing JSONL: " << path << "\n"; return 5; }
  std::string line;
  int count=0;
  while (std::getline(in,line)) {
    // CR-LF line ending support for Windows-built input.
    if (!line.empty() && line.back()=='\r') line.pop_back();
    const bool actual=parse_ok(parser,line);
    if (actual!=expected) {
      std::cerr<< "JSON classification mismatch file=" << path
               << " line=" << count+1 << " expected=" << expected
               << " actual=" << actual << "\n";
      return 20;
    }
    ++count;
  }
  if (count<10) {std::cerr<< "Insufficient correctness coverage in " << path << "\n";return 21;}
  std::cout<<"VALIDATION "<<(expected?"valid":"invalid")<<"="<<count<<"\n";
  return 0;
}
int main(int argc,char** argv) {
  if (argc < 3) {std::cerr<<"usage: bench <rvv|rvv_vls> <validate|split> args...\n";return 2;}
  std::string backend=argv[1], mode=argv[2];
  if (int rc=select_backend(backend)) return rc;
  simdjson::dom::parser parser;
  if (mode=="validate") {
    if (argc!=5) return 2;
    int rc=validate_file(parser,argv[3],true);if (rc) return rc;
    rc=validate_file(parser,argv[4],false);if (rc) return rc;
    std::cout << "RVV_VALIDATION_OK backend=" << backend << "\n";
    return 0;
  }
  if (mode=="check") {
    if(argc!=4) return 2;
    simdjson::padded_string doc;
    if(simdjson::padded_string::load(argv[3]).get(doc)!=simdjson::SUCCESS)return 5;
    simdjson::dom::element elem;
    if(auto rc=parser.parse(doc).get(elem))return 22;
    const std::string canonical=simdjson::to_string(elem);
    std::uint64_t h=14695981039346656037ULL;
    for (unsigned char c:canonical) { h^=c; h*=1099511628211ULL; }
    std::cout<<"CHECK_OK "<<canonical.size()<<" "<<std::hex<<h<<"\n";
    return 0;
  }
  if (mode!="split" || argc!=5) return 2;
  simdjson::padded_string doc;
  if (simdjson::padded_string::load(argv[3]).get(doc)!=simdjson::SUCCESS || doc.size()==0)
    return 5;
  char* end=nullptr;
  long count=std::strtol(argv[4],&end,10);
  if (!end || *end || count<1 || count>1000) return 6;
  // Warm init is required: parser.implementation is created lazily by parse().
  if (!parse_ok(parser,doc)) {std::cerr<<"Corpus fails full DOM parse\n";return 22;}
  const uint8_t* data=reinterpret_cast<const uint8_t*>(doc.data());
  auto stage_cycle = [&]() -> int {
    auto rc=parser.implementation->stage1(data,doc.size(),simdjson::stage1_mode::regular);
    if (rc!=simdjson::SUCCESS) {std::cerr<<"Stage1 error "<<rc<<"\n";return 23;}
    rc=parser.implementation->stage2(parser.doc);
    if (rc!=simdjson::SUCCESS) {std::cerr<<"Stage2 error "<<rc<<"\n";return 24;}
    return 0;
  };
  if (int rc=stage_cycle()) return rc;
  using clock=std::chrono::steady_clock;
  double dom_rates[3],stage1_rates[3],stage2_rates[3];
  double dom_times[3],stage1_times[3],stage2_times[3];
  for (int rep=0;rep<3;rep++) {
    // Measure stages from actual implementation calls, not an inferred split.
    double ns1=0,ns2=0;
    for(long i=0;i<count;i++) {
      const auto t0=clock::now();
      auto rc=parser.implementation->stage1(data,doc.size(),simdjson::stage1_mode::regular);
      const auto t1=clock::now();
      if(rc!=simdjson::SUCCESS) return 30;
      rc=parser.implementation->stage2(parser.doc);
      const auto t2=clock::now();
      if(rc!=simdjson::SUCCESS) return 31;
      ns1+=std::chrono::duration<double>(t1-t0).count();
      ns2+=std::chrono::duration<double>(t2-t1).count();
    }
    const auto start=clock::now();
    for(long i=0;i<count;i++) {
      if(!parse_ok(parser,doc)) {std::cerr<<"Corrupt DOM parse during benchmark\n";return 32;}
    }
    const auto finish=clock::now();
    dom_times[rep]=std::chrono::duration<double>(finish-start).count();
    stage1_times[rep]=ns1;
    stage2_times[rep]=ns2;
    if (dom_times[rep]<=0||ns1<=0||ns2<=0)return 33;
    const double bytes=double(count)*double(doc.size());
    dom_rates[rep]=bytes / dom_times[rep] / 1e9;
    stage1_rates[rep]=bytes / ns1 / 1e9;
    stage2_rates[rep]=bytes / ns2 / 1e9;
  }
  std::sort(dom_rates,dom_rates+3);
  std::sort(stage1_rates,stage1_rates+3);
  std::sort(stage2_rates,stage2_rates+3);
  std::sort(dom_times,dom_times+3);
  std::sort(stage1_times,stage1_times+3);
  std::sort(stage2_times,stage2_times+3);
  std::cout.precision(12);
  std::cout<<"SPLIT_RESULT "<<dom_rates[1]<<' '<<stage1_rates[1]<<' '
           <<stage2_rates[1]<<' '<<dom_times[1]<<' '<<stage1_times[1]
           <<' '<<stage2_times[1]<<' '<<count<<' '<<doc.size()<<"\n";
  return 0;
}
