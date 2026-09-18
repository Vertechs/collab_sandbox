#include "collab_c/math_ops.h"

int collab_add(int a, int b) {
    return a + b;
}

int collab_subtract(int a, int b) {
    return a - b;
}

int collab_multiply(int a, int b) {
    return a * b;
}

int collab_divide(int a, int b) {
    if (b == 0) {
        return 0;
    }
    return a / b;
}
