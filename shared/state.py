class SystemState:

    def __init__(self):

        self.mode = "manual"

        self.pan_angle = 90
        self.tilt_angle = 90

        self.target_x = None
        self.target_y = None

        self.frame_width = 640
        self.frame_height = 480

        self.tracked_id = None