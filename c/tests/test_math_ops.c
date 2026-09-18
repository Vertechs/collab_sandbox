#include <assert.h>
#include "collab_c/math_ops.h"

int main(void) {
    assert(collab_add(2, 3) == 5);
    assert(collab_subtract(10, 4) == 6);
    assert(collab_multiply(3, 4) == 12);
    assert(collab_divide(8, 2) == 4);
    return 0;
}
