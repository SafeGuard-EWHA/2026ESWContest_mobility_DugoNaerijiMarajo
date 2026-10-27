#include "thermal_observer.hpp"
#include <iostream>
int main() {
    safeguard::ThermalObserver observer; safeguard::Config c;
    nlohmann::json result;
    for(int t=0;t<=600;++t) {
        safeguard::InputSnapshot s;s.mode="DEMO";
        s.temperature={true,28+.01*t,double(t),"DEMO"};
        s.ambient={true,25,double(t),"DEMO"};
        result=observer.step(s,t,c,false);
    }
    result["example_type"]="SYNTHETIC_SOFTWARE_EXAMPLE_NOT_VEHICLE_MEASUREMENT";
    std::cout<<result.dump(2)<<'\n';
}
