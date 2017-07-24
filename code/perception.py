"""
Module for rover perception.

Contains functions for processing rover's front camera video frames
and updating rover state

"""

__author__ = 'Salman Hashmi, Ryan Keenan'
__license__ = 'BSD License'


from collections import namedtuple

import numpy as np
import cv2


# GLOBAL CONSTANTS

# rover cam image dimensions
CAM_IMG_WIDTH = 320
CAM_IMG_HEIGT = 160

# destination warped image box where 10x10 pixel square is 1 square meter
DST_GRID_SIZE = 10

# estimated bottom offset to account for bottom of cam image not being
# the position of the rover but a bit in front of it
BOTTOM_OFFSET = 6

# numpy array of four source coordinates on rover camera input 3D image
SRC_POINTS_3D = np.float32([[14, 140], [301, 140], [200, 96], [118, 96]])

# corresponding destination coordinates on output 2D overhead image
DST_POINTS_2D = np.float32([[CAM_IMG_WIDTH/2 - DST_GRID_SIZE/2,
                             CAM_IMG_HEIGT - BOTTOM_OFFSET],
                            [CAM_IMG_WIDTH/2 + DST_GRID_SIZE/2,
                             CAM_IMG_HEIGT - BOTTOM_OFFSET],
                            [CAM_IMG_WIDTH/2 + DST_GRID_SIZE/2,
                             CAM_IMG_HEIGT - DST_GRID_SIZE - BOTTOM_OFFSET],
                            [CAM_IMG_WIDTH/2 - DST_GRID_SIZE/2,
                             CAM_IMG_HEIGT - DST_GRID_SIZE - BOTTOM_OFFSET]])

# scale factor between world frame pixels and rover frame pixels
SCALE_FACTOR = 10

# integer length of the square world map (200 x 200 pixels)
WORLDMAP_HEIGHT = 200


def color_thresh(input_img, rgb_thresh=(160, 160, 160),
                 low_bound=(75, 130, 130), upp_bound=(255, 255, 255)):
    """
    Apply color thresholds to extract pixels of navigable/obstacles/rocks.

    Keyword arguments:
    input_img -- numpy image on which RGB threshold is applied
    rgb_thresh -- RGB thresh tuple above which only ground pixels are detected
    low/up_bounds -- HSV tuples defining color range of gold rock samples

    Return values:
    thresh_imgs -- namedtuple of binary images identifying nav/obs/rock pixels

    """
    # Create arrays of zeros same xy size as input_img, but single channel
    nav_img = np.zeros_like(input_img[:, :, 0])
    obs_img = np.zeros_like(input_img[:, :, 0])

    # Convert BGR input_img to HSV for rock samples
    hsv_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2HSV)

    # Require that each of the R(0), G(1), B(2) pixels be above all three
    # rgb_thresh values such that pixpts_above_thresh will now contain a
    # boolean array with "True" where threshold was met
    pixpts_above_thresh = (
        (input_img[:, :, 0] > rgb_thresh[0]) &
        (input_img[:, :, 1] > rgb_thresh[1]) &
        (input_img[:, :, 2] > rgb_thresh[2])
    )
    pixpts_nonzero = (
        (input_img[:, :, 0] > 0) &
        (input_img[:, :, 1] > 0) &
        (input_img[:, :, 2] > 0)
    )
    # obstacle pixels are those non-zero pixels where rgb_thresh was not met
    obs_pixpts = np.logical_and(pixpts_nonzero,
                                np.logical_not(pixpts_above_thresh))

    # Index the array of zeros with the boolean array and set to 1
    # those pixels where ROI threshold was met
    nav_img[pixpts_above_thresh] = 1
    obs_img[obs_pixpts] = 1

    # Threshold the HSV image to get only colors for gold rock samples
    rock_img = cv2.inRange(hsv_img, low_bound, upp_bound)

    # Return the threshed binary images
    ThreshedImages = namedtuple('ThreshedImages', 'nav obs rock')
    thresh_imgs = ThreshedImages(nav_img, obs_img, rock_img)

    return thresh_imgs


def perspect_transform(input_img):
    """
    Apply a perspective transformation to input 3D image.

    Keyword arguments:
    input_img -- 3D numpy image on which perspective transform is applied

    Return value:
    output_img -- 2D warped numpy image with overhead view

    """
    transform_matrix = cv2.getPerspectiveTransform(
        SRC_POINTS_3D,
        DST_POINTS_2D
    )
    output_img = cv2.warpPerspective(
        input_img,
        transform_matrix,
        (input_img.shape[1], input_img.shape[0])  # keep same size as input_img
    )
    return output_img


def perspect_to_rover(binary_img):
    """
    Transform pixel points from perspective frame to rover frame.

    Keyword argument:
    binary_img -- single channel 2D warped numpy image in perspective frame

    Return value:
    pixpts_rf -- namedtuple of numpy arrays of pixel x,y points in rover frame

    """
    # get image dimensions
    IMG_HEIGHT, IMG_WIDTH = binary_img.shape

    # Identify all nonzero pixel coords in the binary image
    ypix_pts_pf, xpix_pts_pf = binary_img.nonzero()

    # Calculate pixel positions with reference to rover's coordinate
    # frame given that rover front camera itself is at center bottom
    # of the photographed image
    xpix_pts_rf = -(ypix_pts_pf - IMG_HEIGHT).astype(np.float)
    ypix_pts_rf = -(xpix_pts_pf - IMG_WIDTH/2).astype(np.float)

    # Define a named tuple for the three regions of interest
    PixPointsRf = namedtuple('PixPointsRf', 'x y')
    pixpts_rf = PixPointsRf(xpix_pts_rf, ypix_pts_rf)

    return pixpts_rf


def to_polar_coords(pixpts):
    """Convert cartesian coordinates of pixels to polar coordinates."""
    # compute distances and angles of each pixel from rover
    dists_to_pixpts = np.sqrt(pixpts.x**2 + pixpts.y**2)
    angles_to_pixpts = np.arctan2(pixpts.y, pixpts.x)

    return dists_to_pixpts, angles_to_pixpts


def rotate_pixpts(pixpts, angle):
    """
    Geometrically rotate pixel points by specified angle.

    Keyword arguments:
    pixpts -- tuple of numpy arrays of pixel x,y points
    angle -- rotation angle

    Return value:
    pixpts_rot -- namedtuple of numpy arrays of pixel x,y points rotated

    """
    angle_rad = angle * np.pi / 180  # degrees to radians
    xpix_pts, ypix_pts = pixpts

    xpix_pts_rotated = ((xpix_pts * np.cos(angle_rad)) -
                        (ypix_pts * np.sin(angle_rad)))

    ypix_pts_rotated = ((xpix_pts * np.sin(angle_rad)) +
                        (ypix_pts * np.cos(angle_rad)))

    PixPointsRot = namedtuple('PixPointsRot', 'x y')
    pixpts_rot = PixPointsRot(xpix_pts_rotated, ypix_pts_rotated)

    return pixpts_rot


def translate_pixpts(pixpts_rot, rover_pos):
    """
    Geometrically translate rotated pixel points by rover position.

    Keyword arguments:
    pixpts_rot -- namedtuple of numpy arrays of pixel x,y points rotated
    rover_pos -- tuple of rover x,y position in world frame

    Return values:
    pixpts_tran -- namedtuple of numpy arrays of pixel x,y points translated

    """
    rover_x, rover_y = rover_pos

    xpix_pts_translated = (pixpts_rot.x / SCALE_FACTOR) + rover_x
    ypix_pts_translated = (pixpts_rot.y / SCALE_FACTOR) + rover_y

    PixPointsTran = namedtuple('PixPointsTran', 'x y')
    pixpts_tran = PixPointsTran(xpix_pts_translated, ypix_pts_translated)

    return pixpts_tran


def rover_to_world(pixpts_rf, rover_pos, rover_yaw):
    """
    Transform pixel points of ROIs from rover frame to world frame.

    Keyword arguments:
    pixpts_rf -- tuple of numpy arrays of x,y pixel points in rover frame
    rover_pos -- tuple of rover x,y position in world frame
    rover_yaw -- rover yaw angle in world frame

    Return values:
    pixpts_wf -- namedtuple of numpy arrays of pixel x,y points in world frame

    """
    # Apply rotation and translation
    pixpts_rf_rot = rotate_pixpts(pixpts_rf, rover_yaw)
    pixpts_rf_tran = translate_pixpts(pixpts_rf_rot, rover_pos)

    # Clip pixels to be within world_size
    xpix_pts_wf = np.clip(np.int_(pixpts_rf_tran.x), 0, WORLDMAP_HEIGHT - 1)
    ypix_pts_wf = np.clip(np.int_(pixpts_rf_tran.y), 0, WORLDMAP_HEIGHT - 1)

    # Define a named tuple for the points of the three ROIs
    PixPointsWf = namedtuple('PixPointsWf', 'x y')
    pixpts_wf = PixPointsWf(xpix_pts_wf, ypix_pts_wf)

    return pixpts_wf


def inv_translate_pixpts(pixpts_wf, translation):
    """
    Inverse translate pixel points from world frame.

    Keyword arguments:
    pixpts_wf -- namedtuple of numpy arrays of x,y pixel points in world frame
    translation -- tuple of displacements along x,y in world frame

    Return values:
    pixpts_rot -- namedtuple of numpy arrays of pixel x,y points in prior
                  rotated positions
    """
    translation_x, translation_y = translation
    xpix_pts_rotated = (pixpts_wf.x - translation_x) * SCALE_FACTOR
    ypix_pts_rotated = (pixpts_wf.y - translation_y) * SCALE_FACTOR

    PixPointsRot = namedtuple('PixPointsRot', 'x y')
    pixpts_rot = PixPointsRot(xpix_pts_rotated, ypix_pts_rotated)

    return pixpts_rot


def perception_step(Rover):
    """
    Sense environment with rover camera and update rover state accordingly.

    Turns rover camera 3D images into a 2D perspective world-view of the
    rover environment identifying regions of interests and superimposes
    this view on the ground truth worldmap

    """
    # Apply perspective transform to get 2D overhead view of rover cam
    warped_img = perspect_transform(Rover.img)

    # Apply color thresholds to extract pixels of navigable/obstacles/rocks
    thresh_pixpts_pf = color_thresh(warped_img)

    # Update Rover.vision_image (displayed on left side of simulation screen)
    Rover.vision_image[:, :, 0] = thresh_pixpts_pf.obs*135
    Rover.vision_image[:, :, 1] = thresh_pixpts_pf.rock
    Rover.vision_image[:, :, 2] = thresh_pixpts_pf.nav*175

    # Transform pixel coordinates from perspective frame to rover frame
    nav_pixpts_rf = perspect_to_rover(thresh_pixpts_pf.nav)
    obs_pixpts_rf = perspect_to_rover(thresh_pixpts_pf.obs)
    rock_pixpts_rf = perspect_to_rover(thresh_pixpts_pf.rock)

    # Convert above cartesian coordinates to polar coordinates
    Rover.nav_dists, Rover.nav_angles = to_polar_coords(nav_pixpts_rf)
    Rover.obs_dists, Rover.obs_angles = to_polar_coords(obs_pixpts_rf)
    Rover.rock_dists, Rover.rock_angles = to_polar_coords(rock_pixpts_rf)
    # Extract subset of nav_angles that are left of rover heading
    Rover.nav_angles_left = Rover.nav_angles[Rover.nav_angles > 0]

    # Only include pixels within certain distances from rover (for fidelity)
    nav_pixpts_rf = [pts[Rover.nav_dists < 60] for pts in nav_pixpts_rf]
    obs_pixpts_rf = [pts[Rover.obs_dists < 80] for pts in obs_pixpts_rf]
    rock_pixpts_rf = [pts[Rover.rock_dists < 70] for pts in rock_pixpts_rf]

    # Transform pixel points of ROIs from rover frame to world frame
    nav_pixpts_wf = rover_to_world(nav_pixpts_rf, Rover.pos, Rover.yaw)
    obs_pixpts_wf = rover_to_world(obs_pixpts_rf, Rover.pos, Rover.yaw)
    rock_pixpts_wf = rover_to_world(rock_pixpts_rf, Rover.pos, Rover.yaw)

    # Update Rover worldmap (to be displayed on right side of screen)
    Rover.worldmap[obs_pixpts_wf.y, obs_pixpts_wf.x, 0] += 255
    Rover.worldmap[rock_pixpts_wf.y, rock_pixpts_wf.x, 1] += 255
    Rover.worldmap[nav_pixpts_wf.y, nav_pixpts_wf.x, 2] += 255

    return Rover
