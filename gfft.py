"""
GFFT

This package mainly consists of a single function, gfft, which is a generalized
Fourier transformation function that can transform between regularly- or
irregularly-spaced, N-D fields. Gridding and degridding is performed when
irregularly spaced fields are requested. Gridding is only supported for 1-, 2-,
or 3-D fields.
"""

"""
Copyright 2012 Michael Bell, Henrik Junklewitz

This file is part of GFFT.

GFFT is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

GFFT is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with GFFT.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
import warnings

from gfft import gridding

def gfft(inp, in_ax=[], out_ax=[], ftmachine='fft', in_zero_center=True, \
    out_zero_center=True, enforce_hermitian_symmetry=False, W=6, alpha=1.5,\
    verbose=True):

    """
    gfft (Generalized FFT)


    def gfft(inp, in_ax=[], out_ax=[], ftmachine='fft', in_zero_center=True, \
        out_zero_center=True, out_is_real=False, W=6, alpha=1.5)

    This is a generalized Fourier transformation function that can transform
    between regularly- or irregularly-spaced, 1- 2- or 3-D fields. Gridding and
    degridding is performed when irregularly spaced fields are requested.

    input
    ------------------
    inp: The input data to be transformed. This can be a 1-, 2- or 3-D
        (henceforth N-D) numpy array.

    in_ax, out_ax: The axes on which the input/output arrays are defined. There
        are a few options here depending on the types of fields that are to be
        transformed:

        To go from regularly spaced input to regularly spaced output: in can be
            an N-D array, leave in_ax and out_ax blank. No gridding is
            performed, it just does an fft or ifft directly.

        To go from irregularly spaced input to regularly spaced output: in must
            be a list of 1-D arrays, in_ax = [N*array([...])] and
            out_ax = [N*(dx, nx)]. So in_ax is a length N list of numpy arrays
            (each of length len(in)) that contain the coordinates for which the
            input data are defined. out_ax is a length N list of tuples
            containing the number of pixels and size of the pixels in the
            regularly spaced N-D out array. Gridding is performed on the input
            data before performing the fft or ifft.

        To go from regularly spaced input to irregularly spaced output: same as
            above except in_ax and out_ax are reversed. out will always be a 1D
            array. De-gridding is performed.

        To go from irregularly spaced input to irregularly spaced output: This
            gets a bit tricky. In this case either in_ax or out_ax =
            ([N x array([...])], [N x (dx, nx)]) **this is a tuple** and the
            other is just [N x array([...])] as before. In this mode, the code
            grids in, Fourier transforms, then degrids onto the coordinates
            given in out_ax. The N tuples of (nx,dx) are necessary because a
            grid must be defined in the middle even though neither the input or
            output arrays live on a grid. The grid can be defined either for the
            input or output space (which is why either in_ax or out_ax can be
            given as a tuple).

    ftmachine: a length N list of strings, with each entry containing either
        'fft' or 'ifft'. This defines whether an FFT or and IFFT should be
        performed for each axis. So, if you have a 3D dataset and you want to do
        an FFT on the first two axes, but an IFFT on the last, you would pass
        ftmachine=['fft', 'fft', 'ifft']. In principle, we could also make DFTs
        an option here, and the code would just do a DFT rather than gridding.
        For an N-D input array, one could also just use ftmachine='fft' and it
        would do an fft for all axes.

        For now, options include: 'fft', 'ifft', and 'none'.

    in_zero_center/out_zero_center: a length N list of booleans. True indicates
        that the zero frequency is in (or should be in) the central pixel, false
        indicates that it is in pixel 0. Basically this indicates whether
        fftshifts should be performed before and after Fourier transforming. For
        an N-D array, in_zero_center=T would indicate that all axes should have
        the zero channel in the central pixel.

    W, alpha: These are gridding parameters.

    enforce_hermitian_symmetry: A length N list of booleans. If the in array is
        to be gridded, setting this to 'True' indicates that the Hermitian
        conjugate of the input array needs to be generated during gridding.
        This can be set for each axis independently. This is ignored when going
        from a regular grid to another regular grid.


    output
    ------------------
    out: A numpy array that contains the FT or IFT of inp.

    """

    VERSION = "0.2.1"

    if verbose:
        print("gfft v. "+VERSION)

    ############################################################################
    # Set some global variables

    # different modes of operation
    MODE_RR = 0 # regular grid to regular grid
    MODE_IR = 1 # irregular grid to regular grid
    MODE_RI = 2 # regular grid to irregular grid
    MODE_II = 3 # irregular grid to irregular grid

    mode_types = {MODE_RR:"regular to regular (no gridding)", \
        MODE_IR:"irregular to regular (gridding)", \
        MODE_RI:"regular to irregular (de-gridding)", \
        MODE_II:"irregular to irregular (gridding and degridding)"}

    # Different ftmachine options
    FTM_FFT = 'fft'
    FTM_IFFT = 'ifft'
    FTM_NONE = 'none'

    ############################################################################
    # Validate the inputs...

    if type(inp) != np.ndarray:
        raise TypeError('inp must be a numpy array.')

    if type(in_ax) != list and type(in_ax) != tuple:
        raise TypeError('in_ax must be either a list or a tuple.')
    if type(out_ax) != list and type(out_ax) != tuple:
        raise TypeError('out_ax must be either a list or a tuple.')
    if type(out_ax) == tuple and type(in_ax) == tuple:
        raise TypeError('out_ax and in_ax cannot both be tuples')

    if type(in_ax) == tuple and (not validate_iterrable_types(in_ax, list)\
        or len(in_ax) != 2):
            raise TypeError('If in_ax is a tuple, it must contain two lists.')
    if type(out_ax) == tuple and (not validate_iterrable_types(out_ax, list)\
        or len(out_ax) != 2):
            raise TypeError('If out_ax is a tuple, it must contain two lists.')

    if type(in_ax) == tuple and \
        not validate_iterrable_types(in_ax[0], np.ndarray):
            raise TypeError('If in_ax is a tuple, it must contain two lists,' +\
                ' the first of which is a list of arrays.')
    if type(in_ax) == tuple and \
        not validate_iterrable_types(in_ax[1], tuple):
            raise TypeError('If in_ax is a tuple, it must contain two lists,' +\
                ' the second of which is a list of tuples.')

    if type(out_ax) == tuple and \
        not validate_iterrable_types(out_ax[0], np.ndarray):
            raise TypeError('If out_ax is a tuple, it must contain two lists,'+\
                ' the first of which is a list of arrays.')
    if type(out_ax) == tuple and \
        not validate_iterrable_types(out_ax[1], tuple):
            raise TypeError('If out_ax is a tuple, it must contain two lists,'+\
                ' the second of which is a list of tuples.')

    if type(W) != int:
        raise TypeError('W must be an integer.')
    if type(alpha) != float and type(alpha) != int:
        raise TypeError('alpha must be a float or int.')

    if (type(ftmachine) != str and type(ftmachine) != list) or \
        (type(ftmachine) == list and \
        not validate_iterrable_types(ftmachine, str)):
            raise TypeError('ftmachine must be a string or a list of strings.')

    if (type(in_zero_center) != bool and type(in_zero_center) != list) or \
        (type(in_zero_center) == list and \
        not validate_iterrable_types(in_zero_center, bool)):
            raise TypeError('in_zero_center must be a Bool or list of Bools.')

    if (type(out_zero_center) != bool and type(out_zero_center) != list) or \
        (type(out_zero_center) == list and \
        not validate_iterrable_types(out_zero_center, bool)):
            raise TypeError('out_zero_center must be a Bool or list of Bools.')

    if (type(enforce_hermitian_symmetry) != bool and \
        type(enforce_hermitian_symmetry) != list) or \
        (type(enforce_hermitian_symmetry) == list and \
        not validate_iterrable_types(enforce_hermitian_symmetry, bool)):
            raise TypeError('enforce_hermitian_symmetry must be a Bool '\
                +'or list of Bools.')


    ############################################################################
    # figure out how many dimensions we are talking about, and what mode we
    # want to use

    N = 0 # number of dimensions
    mode = -1

    if len(in_ax) == 0:
        # regular to regular transformation
        mode = MODE_RR
        N = inp.ndim
        if len(out_ax) != 0:
            warnings.warn('in_ax is empty, indicating regular to regular '\
                +'transformation is requested, but out_ax is not empty. '+\
                'Ignoring out_ax and proceeding with regular to regular mode.')
    elif type(in_ax)==tuple or type(out_ax)==tuple:
        # irregular to irregular transformation
        mode = MODE_II
        if type(out_ax)==tuple:
            if len(out_ax) != 2:
                raise TypeError('Invalid out_ax for '+\
                    'irregular to irregular mode.')
            N = len(in_ax)
        else:
            if len(in_ax) != 2:
                raise TypeError('Invalid in_ax for '+\
                    'irregular to irregular mode.')
            N = len(out_ax)
    else:
        if type(in_ax[0])==tuple:
            # regular to irregular transformation
            mode = MODE_RI
        else:
            # irregular to regular transformation
            mode = MODE_IR
        N = len(in_ax)
        if len(out_ax) != len(in_ax):
            raise TypeError('For regular to irregular mode, len(in_ax) must '+\
                'equal len(out_ax).')

    if N==0 or mode == -1:
        raise Exception('Something went wrong in setting the mode and ' \
            + 'dimensionality.')

    if N > 3 and mode != MODE_RR:
        raise Exception('Gridding has been requested for an unsupported '+\
            'number of dimensions!')

    if verbose:
        print('Requested mode = ' + mode_types[mode])
        print("Number of dimensions = " + str(N))

    ############################################################################
    # Figure out which axes should have which transforms applied to them

    # flags to determine whether I need to use fftn and/or ifftn
    do_fft = False
    do_ifft = False
    # if you give an empty list to fftn in the axes position, nothing happens
    fftaxes = []
    ifftaxes = []

    if type(ftmachine) == str:
        if ftmachine.lower() == FTM_FFT:
            do_fft = True
            fftaxes = None
        elif ftmachine.lower() == FTM_IFFT:
            do_ifft = True
            ifftaxes = None
    elif type(ftmachine) == list:
        if len(ftmachine) != N:
            raise Exception('ftmachine is a list with invalid length')

        for i in range(len(ftmachine)):
            if ftmachine[i].lower() == FTM_FFT:
                do_fft = True
                fftaxes += [i]
            elif ftmachine[i].lower() == FTM_IFFT:
                do_ifft = True
                ifftaxes += [i]

# As requested by Marco, if no FFT is requested, the function will still
# perform a shift.
    if (do_fft == False and do_ifft == False) or \
        (fftaxes == [] and ifftaxes == []):
            warnings.warn('No Fourier transformation requested, only '+\
                'shifting will be performed!')
#            return
            mode = MODE_RR #Since gridding will not be needed, just use RR mode

    ############################################################################
    # figure out which axes need to be shifted (before and after FT)

    do_preshift = False
    do_postshift = False

    preshift_axes = []
    postshift_axes = []

    if type(in_zero_center) == bool:
        if in_zero_center:
            do_preshift = True
            preshift_axes = None
    elif type(in_zero_center) == list:
        if len(in_zero_center) != N:
            raise Exception('in_zero_center is a list with invalid length')

        for i in range(len(in_zero_center)):
            if in_zero_center[i]:
                do_preshift = True
                preshift_axes += [i]

    if type(out_zero_center) == bool:
        if out_zero_center:
            do_postshift = True
            postshift_axes = None
    elif type(out_zero_center) == list:
        if len(out_zero_center) != N:
            raise Exception('out_zero_center is a list with invalid length')

        for i in range(len(out_zero_center)):
            if out_zero_center[i]:
                do_postshift = True
                postshift_axes += [i]

    ############################################################################
    # figure out which axes need to be hermitianized

    hermitianized_axes = []

    if type(enforce_hermitian_symmetry) == bool:
        if enforce_hermitian_symmetry:
            for i in range(N):
                hermitianized_axes += [True]
        else:
            for i in range(N):
                hermitianized_axes += [False]

    elif type(enforce_hermitian_symmetry) == list:
        if len(enforce_hermitian_symmetry) != N:
            raise Exception('enforce_hermitian_symmetry is a list with '+\
                'invalid length')

        for i in range(len(enforce_hermitian_symmetry)):
            if enforce_hermitian_symmetry[i]:
                hermitianized_axes += [True]
            else:
                hermitianized_axes += [False]

    if len(hermitianized_axes) != N:
        raise Exception('Something went wrong when setting up the '+\
            'hermitianized_axes list!')

    ############################################################################
    # Print operation summary

    if verbose:
        print("")
        print("Axis#, FFT, IFFT, ZCIN, ZCOUT, HERM")

        for i in range(N):
            pstr = str(N)+', '

            if fftaxes == None or fftaxes.count(i)>0:
                pstr = pstr + 'True, '
            else:
                pstr = pstr + 'False, '

            if ifftaxes == None or ifftaxes.count(i)>0:
                pstr = pstr + 'True, '
            else:
                pstr = pstr + 'False, '

            if preshift_axes == None or preshift_axes.count(i)>0:
                pstr = pstr + 'True, '
            else:
                pstr = pstr + 'False, '

            if postshift_axes == None or postshift_axes.count(i)>0:
                pstr = pstr + 'True, '
            else:
                pstr = pstr + 'False, '

            if hermitianized_axes[i]:
                pstr = pstr + 'True'
            else:
                pstr = pstr + 'False'

        print(pstr)

    ############################################################################
    # Do MODE_RR transform

    if mode == MODE_RR:
        if do_preshift:
            inp = np.fft.fftshift(inp, axes=preshift_axes)

        if do_fft:
            out = np.fft.fftn(inp, axes=fftaxes)
        else:
            out = inp.copy()

        if do_ifft:
            out = np.fft.ifftn(out, axes=ifftaxes)

        if do_postshift:
            out = np.fft.fftshift(out, axes=postshift_axes)

        if verbose:
            print("Done!")
            print("")

        return out

    ############################################################################
    # Do MODE_IR transform

    elif mode == MODE_IR:

        # all gridding code assumes the data array is complex
        inp = np.array(inp, dtype=complex)

        # grid
        if N == 1:
            dx = out_ax[0][0]
            Nx = out_ax[0][1]
            xmin = 0.
            if do_postshift:
                xmin = -0.5*Nx*dx
            du = 1./dx/Nx/alpha
            Nu = int(alpha*Nx)
            umin = 0.
            if do_preshift:
                umin = -0.5*Nu*du

            inp_grid = gridding.grid_1d(in_ax[0], inp, du, Nu, umin, alpha, W, \
                hermitianized_axes[0])

        elif N == 2:
            dx = out_ax[0][0]
            Nx = out_ax[0][1]
            xmin = 0.
            du = 1./dx/Nx/alpha
            Nu = int(alpha*Nx)
            umin = 0.

            dy = out_ax[1][0]
            Ny = out_ax[1][1]
            ymin = 0.
            dv = 1./dy/Ny/alpha
            Nv = int(alpha*Ny)
            vmin = 0.

            if do_preshift:
                if preshift_axes == None: #shift all axes
                    vmin = -0.5*Nv*dv
                    umin = -0.5*Nu*du
                else: #only shift some axes...
                    if preshift_axes.count(1) > 0:
                        vmin = -0.5*Nv*dv
                    if preshift_axes.count(0) > 0:
                        umin = -0.5*Nu*du
            if do_postshift:
                if postshift_axes == None: #shift all axes
                    xmin = -0.5*Nx*dx
                    ymin = -0.5*Ny*dy
                else: #only shift some axes...
                    if postshift_axes.count(1) > 0:
                        ymin = -0.5*Ny*dy
                    if postshift_axes.count(0) > 0:
                        xmin = -0.5*Nx*dx

            inp_grid = gridding.grid_2d(in_ax[0], in_ax[1], inp, du, Nu, umin, \
                dv, Nv, vmin, alpha, W, \
                hermitianized_axes[0], hermitianized_axes[1])


        elif N == 3:
            dx = out_ax[0][0]
            Nx = out_ax[0][1]
            xmin = 0.
            du = 1./dx/Nx/alpha
            Nu = int(alpha*Nx)
            umin = 0.

            dy = out_ax[1][0]
            Ny = out_ax[1][1]
            ymin = 0.
            dv = 1./dy/Ny/alpha
            Nv = int(alpha*Ny)
            vmin = 0.

            dz = out_ax[2][0]
            Nz = out_ax[2][1]
            zmin = 0.
            dw = 1./dz/Nz/alpha
            Nw = int(alpha*Nz)
            wmin = 0.


            if do_preshift:
                if preshift_axes == None:
                    vmin = -0.5*Nv*dv
                    umin = -0.5*Nu*du
                    wmin = -0.5*Nw*dw
                else:
                    if preshift_axes.count(1) > 0:
                        vmin = -0.5*Nv*dv
                    if preshift_axes.count(0) > 0:
                        umin = -0.5*Nu*du
                    if preshift_axes.count(2) > 0:
                        wmin = -0.5*Nw*dw
            if do_postshift:
                if postshift_axes == None:
                    xmin = -0.5*Nx*dx
                    ymin = -0.5*Ny*dy
                    zmin = -0.5*Nz*dz
                else:
                    if postshift_axes.count(1) > 0:
                        ymin = -0.5*Ny*dy
                    if postshift_axes.count(0) > 0:
                        xmin = -0.5*Nx*dx
                    if postshift_axes.count(2) > 0:
                        zmin = -0.5*Nz*dz

            inp_grid = gridding.grid_3d(in_ax[0], in_ax[1], in_ax[2], inp, \
                du, Nu, umin, dv, Nv, vmin, dw, Nw, wmin, alpha, W, \
                hermitianized_axes[0], hermitianized_axes[1], \
                hermitianized_axes[2])

        if do_preshift:
            inp_grid = np.fft.fftshift(inp_grid, axes=preshift_axes)

        if do_fft:
            out = np.fft.fftn(inp_grid, axes=fftaxes)
        else:
            out = inp_grid.copy()

        if do_ifft:
            out = np.fft.ifftn(out, axes=ifftaxes)

        # shift
        if do_postshift:
            out = np.fft.fftshift(out, axes=postshift_axes)

        # crop & grid correct
        if N == 1:
            tndxx = int(0.5*Nx*(alpha-1))
            if do_postshift:
                out = out[tndxx:tndxx+Nx]
            else:
                out = out[0:Nx]
            gc = gridding.get_grid_corr_1d(dx, Nx, xmin, du, W, alpha)

        elif N == 2:
            tndxx = int(0.5*Nx*(alpha-1))
            tndxy = int(0.5*Ny*(alpha-1))
            xl = 0
            yl = 0

            if do_postshift:
                if postshift_axes == None:
                    xl = tndxx
                    yl = tndxy
                else:
                    if postshift_axes.count(0)>0:
                        xl = tndxx
                    if postshift_axes.count(1)>0:
                        yl = tndxy

            out = out[int(xl):int(xl+Nx), int(yl):int(yl+Ny)]
            gc = gridding.get_grid_corr_2d(dx, Nx, xmin, dy, Ny, ymin, \
                du, dv, W, alpha)

        elif N == 3:
            tndxx = int(0.5*Nx*(alpha-1))
            tndxy = int(0.5*Ny*(alpha-1))
            tndxz = int(0.5*Nz*(alpha-1))
            xl = 0
            yl = 0
            zl = 0

            if do_postshift:
                if postshift_axes == None:
                    xl = tndxx
                    yl = tndxy
                    zl = tndxz
                else:
                    if postshift_axes.count(0)>0:
                        xl = tndxx
                    if postshift_axes.count(1)>0:
                        yl = tndxy
                    if postshift_axes.count(2)>0:
                        zl = tndxz

            out = out[xl:xl+Nx, yl:yl+Ny, zl:zl+Nz]
            gc = gridding.get_grid_corr_3d(dx, Nx, xmin, dy, Ny, ymin, \
                dz, Nz, zmin, du, dv, dw, W, alpha)

        if verbose:
            print("Done!")
            print("")

        return out/gc

    ############################################################################
    # Do MODE_RI transform

    elif mode == MODE_RI:

        # all gridding code assumes the data array is complex
        inp = np.array(inp, dtype=complex)

        # grid basics
        if N == 1:
            dx = in_ax[0][0]
            Nx = in_ax[0][1]
            xmin = 0.
            if do_preshift:
                xmin = -0.5*Nx*dx
            du = 1./dx/Nx/alpha
            Nu = int(alpha*Nx)
            umin = 0.
            if do_postshift:
                umin = -0.5*Nu*du

        elif N == 2:
            dx = in_ax[0][0]
            Nx = in_ax[0][1]
            xmin = 0.
            du = 1./dx/Nx/alpha
            Nu = int(alpha*Nx)
            umin = 0.

            dy = in_ax[1][0]
            Ny = in_ax[1][1]
            ymin = 0.
            dv = 1./dy/Ny/alpha
            Nv = int(alpha*Ny)
            vmin = 0.

            if do_postshift:
                if postshift_axes == None:
                    vmin = -0.5*Nv*dv
                    umin = -0.5*Nu*du
                else:
                    if postshift_axes.count(1) > 0:
                        vmin = -0.5*Nv*dv
                    if postshift_axes.count(0) > 0:
                        umin = -0.5*Nu*du
            if do_preshift:
                if preshift_axes == None:
                    xmin = -0.5*Nx*dx
                    ymin = -0.5*Ny*dy
                else:
                    if preshift_axes.count(1) > 0:
                        ymin = -0.5*Ny*dy
                    if preshift_axes.count(0) > 0:
                        xmin = -0.5*Nx*dx

        elif N == 3:
            dx = in_ax[0][0]
            Nx = in_ax[0][1]
            xmin = 0.
            du = 1./dx/Nx/alpha
            Nu = int(alpha*Nx)
            umin = 0.

            dy = in_ax[1][0]
            Ny = in_ax[1][1]
            ymin = 0.
            dv = 1./dy/Ny/alpha
            Nv = int(alpha*Ny)
            vmin = 0.

            dz = in_ax[2][0]
            Nz = in_ax[2][1]
            zmin = 0.
            dw = 1./dz/Nz/alpha
            Nw = int(alpha*Nz)
            wmin = 0.

            if do_postshift:
                if postshift_axes == None:
                    vmin = -0.5*Nv*dv
                    umin = -0.5*Nu*du
                    wmin = -0.5*Nw*dw
                else:
                    if postshift_axes.count(1) > 0:
                        vmin = -0.5*Nv*dv
                    if postshift_axes.count(0) > 0:
                        umin = -0.5*Nu*du
                    if postshift_axes.count(2) > 0:
                        wmin = -0.5*Nw*dw
            if do_preshift:
                if preshift_axes == None:
                    xmin = -0.5*Nx*dx
                    ymin = -0.5*Ny*dy
                    zmin = -0.5*Nz*dz
                else:
                    if preshift_axes.count(1) > 0:
                        ymin = -0.5*Ny*dy
                    if preshift_axes.count(0) > 0:
                        xmin = -0.5*Nx*dx
                    if preshift_axes.count(2) > 0:
                        zmin = -0.5*Nz*dz


        # degrid correct & enlargement
        if N == 1:
            tndxx = int(0.5*Nx*(alpha-1))
            inp = inp/gridding.get_grid_corr_1d(dx, Nx, xmin, du, W, alpha)

            inp_oversam = np.zeros(Nu, dtype=complex)

            xl = 0

            if do_preshift:
                xl = tndxx

            inp_oversam[xl:xl+Nx] = inp

        elif N == 2:
            tndxx = int(0.5*Nx*(alpha-1))
            tndxy = int(0.5*Ny*(alpha-1))
            inp = inp/gridding.get_grid_corr_2d(dx, Nx, xmin, dy, Ny, ymin, \
                du, dv, W, alpha)

            inp_oversam = np.zeros((Nu,Nv), dtype=complex)

            xl = 0
            yl = 0

            if do_preshift:
                if preshift_axes == None:
                    xl = tndxx
                    yl = tndxy
                else:
                    if preshift_axes.count(0) > 0:
                        xl = tndxx
                    if preshift_axes.count(1) > 0:
                        yl = tndxy

            inp_oversam[xl:xl+Nx, yl:yl+Ny] = inp


        elif N == 3:
            tndxx = int(0.5*Nx*(alpha-1))
            tndxy = int(0.5*Ny*(alpha-1))
            tndxz = int(0.5*Nz*(alpha-1))
            inp = inp/gridding.get_grid_corr_3d(dx, Nx, xmin, dy, Ny, ymin, \
                dz, Nz, zmin, du, dv, dw, W, alpha)
            inp_oversam = np.zeros((Nu,Nv,Nw), dtype=complex)

            xl = 0
            yl = 0
            zl = 0

            if do_preshift:
                if preshift_axes == None:
                    xl = tndxx
                    yl = tndxy
                    zl = tndxz
                else:
                    if preshift_axes.count(0) > 0:
                        xl = tndxx
                    if preshift_axes.count(1) > 0:
                        yl = tndxy
                    if preshift_axes.count(2) > 0:
                        zl = tndxz

            inp_oversam[xl:xl+Nx, yl:yl+Ny, zl:zl+Nz] = inp

        # shift
        if do_preshift:
            inp_oversam = np.fft.fftshift(inp_oversam, axes=preshift_axes)

        # fft
        if do_fft:
            out = np.fft.fftn(inp_oversam, axes=fftaxes)
        else:
            out = inp_oversam.copy()

        if do_ifft:
            out = np.fft.ifftn(out, axes=ifftaxes)

        # shift
        if do_postshift:
            out = np.fft.fftshift(out, axes=postshift_axes)

        # degrid
        if N == 1:
            out_degrid = gridding.degrid_1d(out_ax[0], out, du, Nu, umin,\
                alpha, W)

        elif N == 2:
            out_degrid = gridding.degrid_2d(out_ax[0], out_ax[1], out, du, Nu, \
                umin, dv, Nv, vmin,  alpha, W)

        elif N == 3:
            out_degrid = gridding.degrid_3d(out_ax[0], out_ax[1], out_ax[2], \
                out, du, Nu, umin, dv, Nv, vmin, dw, Nw, wmin, alpha, W)

        if verbose:
            print("Done!")
            print("")

        return out_degrid

    ############################################################################
    # Do MODE_II transform

    elif mode == MODE_II:

        #defining the grids
        if type(in_ax) == tuple:
            raise Exception("Defining grid on in_ax in MODE_II not yet "\
                +"supported...")
            # everything in here is out of date... needs total overhaul!
            if N == 1:
                du = in_ax[1][0][0]
                Nu = int(in_ax[1][0][1]*alpha )
                umin = 0.
                if do_preshift:
                    umin = -0.5*Nu*du
                dx = 1./du/Nu
                Nx = Nu
                umin = 0.
                if do_postshift:
                    umin = -0.5*Nu*du

                in_ax = in_ax[0]

            elif N == 2:
                dx = in_ax[1][0][0]
                Nx = in_ax[1][0][1]
                xmin = 0.
                if type(in_zero_center)==bool and in_zero_center==True:
                    xmin = -0.5*Nx*dx
                elif in_zero_center[0] == True:
                    xmin = -0.5*Nx*dx
                du = 1./dx/Nx/alpha
                Nu = int(alpha*Nx)
                umin = 0.
                if do_postshift:
                    umin = -0.5*Nu*du

                dy = in_ax[1][1][0]
                Ny = in_ax[1][1][1]
                ymin = 0.
                if type(in_zero_center)==bool and in_zero_center==True:
                    ymin = -0.5*Ny*dy
                elif in_zero_center[1] == True:
                    ymin = -0.5*Ny*dy
                dv = 1./dy/Ny/alpha
                Nv = int(alpha*Ny)
                vmin = 0.
                if do_postshift:
                    vmin = -0.5*Nv*dv

                in_ax = in_ax[0]

            elif N == 3:
                dx = in_ax[1][0][0]
                Nx = in_ax[1][0][1]
                xmin = 0.
                if type(in_zero_center)==bool and in_zero_center==True:
                    xmin = -0.5*Nx*dx
                elif in_zero_center[0] == True:
                    xmin = -0.5*Nx*dx
                du = 1./dx/Nx/alpha
                Nu = int(alpha*Nx)
                umin = 0.
                if do_postshift:
                    umin = -0.5*Nu*du

                dy = in_ax[1][1][0]
                Ny = in_ax[1][1][1]
                ymin = 0.
                if type(in_zero_center)==bool and in_zero_center==True:
                    ymin = -0.5*Ny*dy
                elif in_zero_center[1] == True:
                    ymin = -0.5*Ny*dy
                dv = 1./dy/Ny/alpha
                Nv = int(alpha*Ny)
                vmin = 0.
                if do_postshift:
                    vmin = -0.5*Nv*dv

                dz = in_ax[1][2][0]
                Nz = in_ax[1][2][1]
                zmin = 0.
                if type(in_zero_center)==bool and in_zero_center==True:
                    zmin = -0.5*Nz*dz
                elif in_zero_center[2] == True:
                    zmin = -0.5*Nz*dz
                dw = 1./dz/Nz/alpha
                Nw = int(alpha*Nz)
                wmin = 0.
                if do_postshift:
                    wmin = -0.5*Nw*dw

                in_ax = in_ax[0]

        else:

            if N == 1:
                dx = out_ax[1][0][0]
                Nx = out_ax[1][0][1]
                xmin = 0.
                if do_postshift:
                    xmin = -0.5*Nx*dx
                du = 1./dx/Nx/alpha
                Nu = int(Nx*alpha)
                umin = 0.
                if do_preshift:
                    umin = -0.5*Nu*du

                out_ax = out_ax[0]

            elif N == 2:
                dx = out_ax[1][0][0]
                Nx = out_ax[1][0][1]
                xmin = 0.
                du = 1./dx/Nx/alpha
                Nu = int(alpha*Nx)
                umin = 0.

                dy = out_ax[1][1][0]
                Ny = out_ax[1][1][1]
                ymin = 0.
                dv = 1./dy/Ny/alpha
                Nv = alpha*Ny
                vmin = 0.

                if do_preshift:
                    if preshift_axes == None:
                        vmin = -0.5*Nv*dv
                        umin = -0.5*Nu*du
                    else:
                        if preshift_axes.count(1) > 0:
                            vmin = -0.5*Nv*dv
                        if preshift_axes.count(0) > 0:
                            umin = -0.5*Nu*du
                if do_postshift:
                    if postshift_axes == None:
                        xmin = -0.5*Nx*dx
                        ymin = -0.5*Ny*dy
                    else:
                        if postshift_axes.count(1) > 0:
                            ymin = -0.5*Ny*dy
                        if postshift_axes.count(0) > 0:
                            xmin = -0.5*Nx*dx

                out_ax = out_ax[0]


            elif N == 3:
                dx = out_ax[1][0][0]
                Nx = out_ax[1][0][1]
                xmin = 0.
                du = 1./dx/Nx/alpha
                Nu = int(alpha*Nx)
                umin = 0.

                dy = out_ax[1][1][0]
                Ny = out_ax[1][1][1]
                ymin = 0.
                dv = 1./dy/Ny/alpha
                Nv = alpha*Ny
                vmin = 0.

                dz = out_ax[1][2][0]
                Nz = out_ax[1][2][1]
                zmin = 0.
                dw = 1./dz/Nz/alpha
                Nw = alpha*Nz
                wmin = 0.

                if do_preshift:
                    if preshift_axes == None:
                        vmin = -0.5*Nv*dv
                        umin = -0.5*Nu*du
                        wmin = -0.5*Nw*dw
                    else:
                        if preshift_axes.count(1) > 0:
                            vmin = -0.5*Nv*dv
                        if preshift_axes.count(0) > 0:
                            umin = -0.5*Nu*du
                        if preshift_axes.count(2) > 0:
                            wmin = -0.5*Nw*dw
                if do_postshift:
                    if postshift_axes == None:
                        xmin = -0.5*Nx*dx
                        ymin = -0.5*Ny*dy
                        zmin = -0.5*Nz*dz
                    else:
                        if postshift_axes.count(1) > 0:
                            ymin = -0.5*Ny*dy
                        if postshift_axes.count(0) > 0:
                            xmin = -0.5*Nx*dx
                        if postshift_axes.count(2) > 0:
                            zmin = -0.5*Nz*dz

                out_ax = out_ax[0]

        # all gridding code assumes the data array is complex
        inp = np.array(inp, dtype=complex)

        # grid
        if N == 1:
            inp_grid = gridding.grid_1d(in_ax[0], inp, du, Nu, umin, alpha, W, \
                hermitianized_axes[0])
        elif N == 2:
            inp_grid = gridding.grid_2d(in_ax[0], in_ax[1], inp, du, Nu, umin, \
                dv, Nv, vmin, W, alpha, \
                hermitianized_axes[0], hermitianized_axes[1])
        elif N == 3:
            inp_grid = gridding.grid_3d(in_ax[0], in_ax[1], in_ax[2], inp, \
                du, Nu, umin, dv, Nv, vmin, dw, Nw, wmin, W, alpha, \
                hermitianized_axes[0], hermitianized_axes[1], \
                hermitianized_axes[2])

        # degrid correct
        if N == 1:
            inp_grid = inp_grid/gridding.get_grid_corr_1d(du, Nu, umin, \
                dx/alpha, W, alpha)

            inp_grid_os = np.zeros(Nu*alpha, dtype=complex)

            ul = 0
            if do_preshift:
                ul = 0.5*Nu*(alpha-1.)

            inp_grid_os[ul:ul+Nu] = inp_grid
            inp_grid = inp_grid_os
            del inp_grid_os

        elif N == 2:
            inp_grid = inp_grid/gridding.get_grid_corr_2d(du, Nu, umin, \
                dv, Nv, vmin, dx/alpha, dy/alpha, W, alpha)

            inp_grid_os = np.zeros((Nu*alpha, Nv*alpha), dtype=complex)

            ul = 0
            vl = 0

            if do_preshift:
                if preshift_axes == None:
                    ul = 0.5*Nu*(alpha-1.)
                    vl = 0.5*Nv*(alpha-1.)
                else:
                    if preshift_axes.count(0) > 0:
                        ul = 0.5*Nu*(alpha-1.)
                    if preshift_axes.count(1) > 0:
                        vl = 0.5*Nv*(alpha-1.)

            inp_grid_os[ul:ul+Nu, vl:vl+Nv] = inp_grid
            inp_grid = inp_grid_os
            del inp_grid_os

        elif N == 3:
            inp_grid = inp_grid/gridding.get_grid_corr_3d(du, Nu, umin, \
                dv, Nv, vmin, dw, Nw, wmin, dx/alpha, dy/alpha, dz/alpha, \
                W, alpha)

            inp_grid_os = np.zeros((Nu*alpha, Nv*alpha, Nw*alpha), \
                dtype=complex)

            ul = 0
            vl = 0
            wl = 0

            if do_preshift:
                if preshift_axes == None:
                    ul = 0.5*Nu*(alpha-1.)
                    vl = 0.5*Nv*(alpha-1.)
                    wl = 0.5*Nw*(alpha-1.)
                else:
                    if preshift_axes.count(0) > 0:
                        ul = 0.5*Nu*(alpha-1.)
                    if preshift_axes.count(1) > 0:
                        vl = 0.5*Nv*(alpha-1.)
                    if preshift_axes.count(2) > 0:
                        wl = 0.5*Nw*(alpha-1.)

            inp_grid_os[ul:ul+Nu, vl:vl+Nv, wl:wl+Nw] = inp_grid
            inp_grid = inp_grid_os
            del inp_grid_os

        # shift
        if do_preshift:
            inp_grid = np.fft.fftshift(inp_grid, axes=preshift_axes)

        # fft
        if do_fft:
            out = np.fft.fftn(inp_grid, axes=fftaxes)
        else:
            out = inp_grid.copy()

        if do_ifft:
            out = np.fft.ifftn(out, axes=ifftaxes)

        # shift
        if do_postshift:
            out = np.fft.fftshift(out, axes=postshift_axes)

        # grid correct
        if N == 1:
#            print "Now here..."
#            print len(out)
#            print alpha**2*Nx
            out = out/gridding.get_grid_corr_1d(dx/alpha, alpha**2*Nx, \
                alpha*xmin, du, W, alpha)

        elif N == 2:
            out = out/gridding.get_grid_corr_2d(dx/alpha, alpha**2*Nx, \
                alpha*xmin, dy/alpha, alpha**2*Ny, alpha*ymin, \
                du, dv, W, alpha)

        elif N == 3:
            out = out/gridding.get_grid_corr_3d(dx/alpha, alpha**2*Nx, \
                alpha*xmin, dy/alpha, alpha**2*Ny, alpha*ymin, \
                dz/alpha, alpha**2*Nz, alpha*zmin, du, dv, dw, W, alpha)

        # degrid
        if N == 1:
            out_degrid = gridding.degrid_1d(out_ax[0], out, dx/alpha, \
                alpha**2*Nx, alpha*xmin, alpha, W)

        elif N == 2:
            out_degrid = gridding.degrid_2d(out_ax[0], out_ax[1], out, \
                dx/alpha, alpha**2*Nx, alpha*xmin, dy/alpha, alpha**2*Ny, \
                alpha*ymin, alpha, W)

        elif N == 3:
            out_degrid = gridding.degrid_3d(out_ax[0], out_ax[1], out_ax[2], \
                out, dx/alpha, alpha**2*Nx, alpha*xmin, dy/alpha, alpha**2*Ny, \
                alpha*ymin, dz/alpha, alpha**2*Nz, alpha*zmin, alpha, W)

        if verbose:
            print("Done!")
            print("")

        return out_degrid


def validate_iterrable_types(l, t):
    """
    Used to check whether the types of the items within the list or tuple l are
    of the type t. Returns True if all items are of type t, False otherwise.
    """

    is_valid = True

    for i in range(len(l)):
        if type(l[i]) != t:
            is_valid = False

    return is_valid


def dft(in_vals, in_ax, out_ax):
    """
    A function that transforms a list of values using a discrete Fourier
    transformation. Works for arbitrary number of dimensions.

    in_ax/out_ax must be a list of numpy arrays, one array for each axis.
    """

    nax = len(in_ax)
    if len(out_ax) != len(in_ax):
        raise Exception('dft: number of input and output dimensions not equal!')

    nin = len(in_vals)
    nout = len(out_ax[0])

    for i in range(nax):
        if len(in_ax[i]) != nin:
            raise Exception('dft: input axis length invalid')
        if len(out_ax[i]) != nout:
            raise Exception('dft: output axis length invalid')

    out_vals = np.zeros(nout, dtype=complex)

    for i in range(nout):
        val = complex(0,0)
        for j in range(nin):
            psum = 0
            for k in range(nax):
                psum += in_ax[k][j]*out_ax[k][i]
            cphs = -2.*np.pi*psum
            val += in_vals[j]*complex(np.cos(cphs),np.sin(cphs))
        out_vals[i] = val
#        progress(20, i+1., nk)

    return out_vals/len(in_vals)

def idft(in_vals, in_ax, out_ax):
    """
    A function that transforms a list of values using a discrete Fourier
    transformation. Works for arbitrary number of dimensions.

    in_ax/out_ax must be a list of numpy arrays, one array for each axis.
    """

    nax = len(in_ax)
    if len(out_ax) != len(in_ax):
        raise Exception('dft: number of input and output dimensions not equal!')

    nin = len(in_vals)
    nout = len(out_ax[0])

    for i in range(nax):
        if len(in_ax[i]) != nin:
            raise Exception('dft: input axis length invalid')
        if len(out_ax[i]) != nout:
            raise Exception('dft: output axis length invalid')

    out_vals = np.zeros(nout, dtype=complex)

    for i in range(nout):
        val = complex(0,0)
        for j in range(nin):
            psum = 0
            for k in range(nax):
                psum += in_ax[k][j]*out_ax[k][i]
            cphs = 2.*np.pi*psum
            val += in_vals[j]*complex(np.cos(cphs),np.sin(cphs))
        out_vals[i] = val
#        progress(20, i+1., nk)

    return out_vals/len(in_vals)
