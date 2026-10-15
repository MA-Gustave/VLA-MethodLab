// Test97 common PUBLIC-API-only simdjson DOM benchmark.
// Built unchanged for official upstream releases and for the experimental RVV fork.
#include "simdjson.h"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

static int set_backend(const char *name) {
  const auto *impl=simdjson::get_available_implementations()[name];
  if (!impl || !impl->supported_by_runtime_system()) {
    std::cerr << "BACKEND_NOT_AVAILABLE " << name << "\n";
    return 3;
  }
  simdjson::get_active_implementation()=impl;
  if (simdjson::get_active_implementation()->name()!=std::string(name)) return 4;
  return 0;
}
static std::uint64_t hash_text(const std::string &s) {
  std::uint64_t h=14695981039346656037ULL;
  for (unsigned char c:s) {h^=c;h*=1099511628211ULL;}
  return h;
}
int main(int argc,char**argv) {
  if(argc<4) {std::cerr << "Usage: benchmark <fallback|rvv> <check|bench|validate> file [iterations]\n";return 2;}
  if(int e=set_backend(argv[1]))return e;
  const std::string mode=argv[2];
  if(mode=="validate") {
    std::ifstream f(argv[3]);if(!f)return 5;
    std::string line;int valid=0,invalid=0;
    while(std::getline(f,line)) {
      if(line.empty())continue;
      if(line.back()=='\r')line.pop_back();
      const bool expected=line[0]=='+';
      if(line[0]!='+' && line[0]!='-')return 6;
      const std::string text=line.substr(1);
      simdjson::dom::parser parser;
      bool actual=parser.parse(text).error()==simdjson::SUCCESS;
      if(actual!=expected) {std::cerr<<"VALIDATION_FAILED line "<<(valid+invalid+1)<<"\n";return 7;}
      if(expected)valid++;else invalid++;
    }
    if(valid<10 || invalid<10)return 8;
    std::cout<<"VALIDATION_OK "<<valid<<" "<<invalid<<"\n";return 0;
  }
  simdjson::padded_string json;
  if(simdjson::padded_string::load(argv[3]).get(json)!=simdjson::SUCCESS || json.size()==0)return 10;
  simdjson::dom::parser parser;
  simdjson::dom::element element;
  if(auto err=parser.parse(json).get(element)) {std::cerr<<"INVALID_JSON "<<err<<"\n";return 11;}
  if(mode=="check") {
    const std::string canonical=simdjson::to_string(element);
    std::cout<<"CHECK_OK "<<canonical.size()<<" "<<std::hex<<hash_text(canonical)<<"\n";
    return 0;
  }
  if(mode!="bench" || argc!=5)return 12;
  char*end=nullptr;long iters=std::strtol(argv[4],&end,10);
  if(!end || *end || iters<1 || iters>1000)return 13;
  using clk=std::chrono::steady_clock;
  volatile std::uint64_t errors=0;
  for(int i=0;i<8;i++)errors+=parser.parse(json).error()!=simdjson::SUCCESS;
  std::vector<double> speeds;
  for(int rep=0;rep<5;rep++) {
    const auto start=clk::now();
    for(long i=0;i<iters;i++)errors+=parser.parse(json).error()!=simdjson::SUCCESS;
    const auto endtime=clk::now();
    const double sec=std::chrono::duration<double>(endtime-start).count();
    if(sec<=0)return 14;
    speeds.push_back(double(json.size())*iters/sec/1e9);
  }
  if(errors)return 15;
  std::sort(speeds.begin(),speeds.end());
  std::cout<<std::setprecision(12)<<"BENCH_OK "<<speeds[2]<<" "<<json.size()<<" "<<iters<<"\n";
  return 0;
}
