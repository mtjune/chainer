import numpy

from chainer import cuda
from chainer import function
from chainer.utils import type_check


class Gaussian(function.Function):

    """Gaussian sampling function.

    It takes mean and log(variance) as input and output sample drawn from
    gaussian N(mean, variance).

    """

    def __init__(self):
        self.eps = None

    def check_type_forward(self, in_types):
        type_check.expect(in_types.size() == 2)

        m_type, v_type = in_types
        type_check.expect(
            m_type.dtype == numpy.float32,
            v_type.dtype == numpy.float32,
            m_type.shape == v_type.shape,
        )

    def check_type_fbackward(self, in_types, out_types):
        type_check.expect(out_types.size() == 1)
        m_type, v_type = in_types
        g_type, = out_types

        type_check.expect(
            g_type.dtype == numpy.float32,
            g_type.shape == m_type.shape,
        )

    def check_type_backward(self, in_types, out_types):
        type_check.expect(out_types.size() == 1)

    def forward_cpu(self, inputs):
        mean, ln_var = inputs
        if self.eps is None:
            self.eps = numpy.random.normal(0, 1, ln_var.shape) \
                                   .astype(numpy.float32)

        self.noise = numpy.exp(ln_var * 0.5) * self.eps
        return mean + self.noise,

    def forward_gpu(self, inputs):
        mean, ln_var = inputs
        if self.eps is None:
            self.eps = cuda.empty(ln_var.shape, numpy.float32)
            cuda.get_generator().fill_normal(self.eps)

        noise = cuda.empty_like(ln_var)
        cuda.elementwise(
            'float* noise, const float* v, const float* e',
            'noise[i] = __expf(v[i] * 0.5f) * e[i];',
            'gaussian_forward'
        )(noise, ln_var, self.eps)
        self.noise = noise
        return mean + self.noise,

    def backward(self, inputs, grad_output):
        g, = grad_output
        return g, g * self.noise * 0.5,


def gaussian(mean, ln_var):
    return Gaussian()(mean, ln_var)
