#!/usr/bin/env python3

import torch
from .kernel import Kernel
from ..lazy import KroneckerProductLazyTensor
from .polynomial_kernel import PolynomialKernel
from typing import Optional
from ..priors import Prior
from ..constraints import Positive, Interval


class PolynomialKernelGrad(PolynomialKernel):
    def forward(
        self,
        x1: torch.Tensor,
        x2: torch.Tensor,
        diag: Optional[bool] = False,
        last_dim_is_batch: Optional[bool] = False,
        **params
    ) -> torch.Tensor:
        offset = self.offset.view(*self.batch_shape, 1, 1)

        batch_shape = x1.shape[:-2]
        n1, d = x1.shape[-2:]
        n2 = x2.shape[-2]

        K = torch.zeros(*batch_shape, n1 * (d + 1), n2 * (d + 1), device=x1.device, dtype=x1.dtype)

        if last_dim_is_batch:
            x1 = x1.transpose(-1, -2).unsqueeze(-1)
            x2 = x2.transpose(-1, -2).unsqueeze(-1)

        if diag:
            raise RuntimeError("None done yet")
            K11 = ((x1 * x2).sum(dim=-1) + self.offset).pow(self.power)
        else:
            base_inner_prod = torch.matmul(x1, x2.transpose(-2, -1)) + offset
            K11 = base_inner_prod.pow(self.power)

            K21_base = (self.power * base_inner_prod.pow(self.power - 1))

            K12 = (K21_base.unsqueeze(-2).transpose(-2, -1) * x1.unsqueeze(-2)).view(*batch_shape, n1, -1)

            K21 = (K21_base.unsqueeze(-2).permute(-1, -3, -2) * x2.unsqueeze(-2))
            K21 = K21.contiguous().view(*batch_shape, n2, -1).transpose(-2, -1)

            all_outers = x1.unsqueeze(-2).unsqueeze(-2).transpose(-2, -1).matmul(x2.unsqueeze(-3).unsqueeze(-2))
            K22_base = base_inner_prod.pow(self.power - 2) * (self.power) * (self.power - 1)
            K22 = (K22_base.unsqueeze(-1).unsqueeze(-1) * all_outers).transpose(-3, -2).contiguous().view(n1 * d, n2 * d)

            kp = KroneckerProductLazyTensor(
                torch.eye(d, d, device=x1.device, dtype=x1.dtype).repeat(*batch_shape, 1, 1),
                K21_base,
            )

            K22 = K22 + kp.evaluate()

            K = torch.cat([torch.cat([K11, K12], dim=-1), torch.cat([K21, K22], dim=-1)])

            # pi1 = torch.arange(n1 * (d + 1)).view(d + 1, n1).t().contiguous().view((n1 * (d + 1)))
            # pi2 = torch.arange(n2 * (d + 1)).view(d + 1, n2).t().contiguous().view((n2 * (d + 1)))
            # K = K[..., pi1, :][..., :, pi2]

            return K

    def num_outputs_per_input(self, x1, x2):
        return x1.size(-1) + 1
