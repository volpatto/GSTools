# -*- coding: utf-8 -*-
"""
GStools subpackage providing generators for spatial random fields.

.. currentmodule:: gstools.field.generator

The following classes are provided

.. autosummary::
   RandMeth
"""
from __future__ import division, absolute_import, print_function

from copy import deepcopy as dcp
import numpy as np
from gstools.covmodel.base import CovModel
from gstools.random.rng import RNG

__all__ = ["RandMeth"]


class RandMeth(object):
    r"""Randomization method for calculating isotropic spatial random fields.

    Notes
    -----
    The Randomization method is used to generate isotropic
    spatial random fields characterized by a given covariance model.
    The calculation looks like:

    .. math::
       u\left(x\right)=
       \sqrt{\frac{\sigma^{2}}{N}}\cdot
       \sum_{i=1}^{N}\left(
       Z_{1,i}\cdot\cos\left(\left\langle k_{i},x\right\rangle \right)+
       Z_{2,i}\cdot\sin\left(\left\langle k_{i},x\right\rangle \right)
       \right)

    where:

        * :math:`N` : fourier mode number
        * :math:`Z_{j,i}` : random samples from a normal distribution
        * :math:`k_i` : samples from the spectral density distribution of
          the covariance model

    Attributes
    ----------
        model : :class:`gstools.CovModel`
            covariance model
        mode_no : :class:`int`, optional
            number of Fourier modes. Default: 1000
        seed : :class:`int`
            the seed of the random number generator.
            If "None", a random seed is used. Default: None
        chunk_tmp_size : :class:`int`
            Number of points (number of coordinates * mode_no)
            to be handled by one chunk while creating the fild.
            This is used to prevent memory overflows while
            generating the field. Default: 1e7
    """

    def __init__(
        self,
        model,
        mode_no=1000,
        seed=None,
        chunk_tmp_size=1e7,
        verbose=False,
        **kwargs
    ):
        """Initialize the randomization method

        Parameters
        ----------
            model : :class:`gstools.CovModel`
                covariance model
            mode_no : :class:`int`, optional
                number of Fourier modes. Default: 1000
            seed : :class:`int`, optional
                the seed of the random number generator.
                If "None", a random seed is used. Default: None
            chunk_tmp_size : :class:`int`, optional
                Number of points (number of coordinates * mode_no)
                to be handled by one chunk while creating the fild.
                This is used to prevent memory overflows while
                generating the field. Default: 1e7
            **kwargs
                Placeholder for keyword-args
        """
        if kwargs:
            print("gstools.RandMeth: **kwargs are ignored")
        # initialize atributes
        self._mode_no = mode_no
        self.chunk_tmp_size = chunk_tmp_size
        self.verbose = verbose
        # initialize private atributes
        self._model = None
        self._seed = None
        self._rng = None
        self._z_1 = None
        self._z_2 = None
        self._cov_sample = None
        # set model and seed
        self.update(model, seed)

    def update(self, model, seed=np.nan):
        """Update the model and the generated modes.

        If model and seed are not different, nothing will be done.

        Parameters
        ----------
            model : :class:`gstools.CovModel`
                covariance model
            seed : :class:`int` or None or np.nan, optional
                the seed of the random number generator.
                If "None", a random seed is used. If "np.nan", the actual seed
                will be kept. Default: np.nan
        """
        if isinstance(model, CovModel):
            if self.model != model:
                self._model = dcp(model)
                if seed is None or not np.isnan(seed):
                    self._set_seed(seed)
                else:
                    self._set_seed(self._seed)
        else:
            raise ValueError(
                "gstools.field.generator.RandMeth: 'model' is not an "
                + "instance of 'gstools.CovModel'"
            )

    def reset_seed(self, seed=None):
        """Reset the random amplitudes and wave numbers with a new seed.

        Parameters
        ----------
            seed : :class:`int`, optional
                the seed of the random number generator.
                If "None", a random seed is used. Default: None
        """
        self._seed = np.nan
        self.seed = seed

    def __call__(self, x, y=None, z=None):
        """Calculates the random modes for the randomization method.

        Parameters
        ----------
            x : :class:`float`, :class:`numpy.ndarray`
                the x components of the position tuple, the shape has to be
                (len(x), 1, 1) for 3d and accordingly shorter for lower
                dimensions
            y : :class:`float`, :class:`numpy.ndarray`, optional
                the y components of the pos. tupls
            z : :class:`float`, :class:`numpy.ndarray`, optional
                the z components of the pos. tuple
        Returns
        -------
            :class:`numpy.ndarray`
                the random modes
        """
        summed_modes = np.broadcast(x, y, z)
        summed_modes = np.squeeze(np.zeros(summed_modes.shape))
        # make a guess fo the chunk_no according to the input
        tmp_pnt = np.prod(summed_modes.shape) * self._mode_no
        chunk_no_exp = int(
            max(0, np.ceil(np.log2(tmp_pnt / self.chunk_tmp_size)))
        )
        # Test to see if enough memory is available.
        # In case there isn't, divide Fourier modes into 2 smaller chunks
        while True:
            try:
                chunk_no = 2 ** chunk_no_exp
                chunk_len = int(np.ceil(self._mode_no / chunk_no))
                if self.verbose:
                    print(
                        "RandMeth: Generating field with "
                        + str(chunk_no)
                        + " chunks"
                    )
                    print("(chunk length " + str(chunk_len) + ")")
                for chunk in range(chunk_no):
                    if self.verbose:
                        print(
                            "chunk " + str(chunk + 1) + " of " + str(chunk_no)
                        )
                    ch_start = chunk * chunk_len
                    # In case k[d,ch_start:ch_stop] with
                    # ch_stop >= len(k[d,:]) causes errors in
                    # numpy, use the commented min-function below
                    # ch_stop = min((chunk + 1) * chunk_len, self._mode_no-1)
                    ch_stop = (chunk + 1) * chunk_len

                    if self.dim == 1:
                        phase = self._cov_sample[0, ch_start:ch_stop] * x
                    elif self.dim == 2:
                        phase = (
                            self._cov_sample[0, ch_start:ch_stop] * x
                            + self._cov_sample[1, ch_start:ch_stop] * y
                        )
                    else:
                        phase = (
                            self._cov_sample[0, ch_start:ch_stop] * x
                            + self._cov_sample[1, ch_start:ch_stop] * y
                            + self._cov_sample[2, ch_start:ch_stop] * z
                        )
                    summed_modes += np.squeeze(
                        np.sum(
                            self._z_1[ch_start:ch_stop] * np.cos(phase)
                            + self._z_2[ch_start:ch_stop] * np.sin(phase),
                            axis=-1,
                        )
                    )
            except MemoryError:
                chunk_no_exp += 1
                print(
                    "Not enough memory. Dividing Fourier modes into {} "
                    "chunks.".format(2 ** chunk_no_exp)
                )
            else:
                # we break out of the endless loop if we don't get MemoryError
                break

        # generate normal distributed values for the nugget simulation
        if self.model.nugget > 0:
            nugget = np.sqrt(self.model.nugget) * self._rng.random.normal(
                size=summed_modes.shape
            )
        else:
            nugget = 0.0

        return np.sqrt(self.model.var / self._mode_no) * summed_modes + nugget

    def _set_seed(self, new_seed):
        """Set a new seed for the random number generation."""
        self._seed = new_seed
        self._rng = RNG(self._seed)
        # normal distributed samples for randmeth
        self._z_1 = self._rng.random.normal(size=self._mode_no)
        self._z_2 = self._rng.random.normal(size=self._mode_no)
        # sample uniform on a sphere
        sphere_coord = self._rng.sample_sphere(self.dim, self._mode_no)
        # sample radii acording to radial spectral density of the model
        if self.model.has_ppf:
            pdf, cdf, ppf = self.model.dist_func
            rad = self._rng.sample_dist(
                size=self._mode_no, pdf=pdf, cdf=cdf, ppf=ppf, a=0
            )
        else:
            rad = self._rng.sample_ln_pdf(
                ln_pdf=self.model.ln_spectral_rad_pdf,
                size=self._mode_no,
                sample_around=1.0 / self.model.len_scale,
            )
        # get fully spatial samples by multiplying sphere samples and radii
        self._cov_sample = rad * sphere_coord

    @property
    def seed(self):
        """:class:`int`: the seed of the master RNG

        Notes
        -----
        If a new seed is given, the setter property not only saves the
        new seed, but also creates new random modes with the new seed.
        """
        return self._seed

    @seed.setter
    def seed(self, new_seed=None):
        """ Set a new seed for the random number generation, if it differs."""
        if new_seed is not self._seed:
            self._set_seed(new_seed)

    @property
    def dim(self):
        """ The dimension of the spatial random field."""
        return self.model.dim

    @property
    def model(self):
        """ The covariance model of the spatial random field."""
        return self._model

    @model.setter
    def model(self, model):
        """ Set a new covariance model and generate new random numbers."""
        self.update(model)

    @property
    def mode_no(self):
        """ The number of modes."""
        return self._mode_no

    @mode_no.setter
    def mode_no(self, mode_no):
        """ Set a new mode number and generate new random numbers."""
        self._mode_no = mode_no
        self._set_seed(self._seed)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "RandMeth(model={0}, mode_no={1}, seed={2})".format(
            repr(self.model), self._mode_no, self.seed
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()