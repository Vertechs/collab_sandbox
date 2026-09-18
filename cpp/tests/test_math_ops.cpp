#include <cassert>
#include <stdexcept>

#include "collab_cpp/math_ops.hpp"

int main() {
    assert(collab_cpp::add(2, 3) == 5);
    assert(collab_cpp::subtract(10, 4) == 6);
    assert(collab_cpp::multiply(3, 4) == 12);
    assert(collab_cpp::divide(8, 2) == 4);

    bool threw = false;
    try {
        collab_cpp::divide(1, 0);
    } catch (const std::overflow_error&) {
        threw = true;
    }
    assert(threw);
    return 0;
}
