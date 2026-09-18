#include "collab_cpp/math_ops.hpp"

namespace collab_cpp {

int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}

int multiply(int a, int b) {
    return a * b;
}

int divide(int a, int b) {
    if (b == 0) {
        throw std::overflow_error("division by zero");
    }
    return a / b;
}

}  // namespace collab_cpp
