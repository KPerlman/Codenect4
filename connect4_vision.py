import cv2
import numpy as np
import sys

class Connect4Tracker:
    def __init__(self):
        ### COLOR CONFIGURATION
        # adjust these if blue board isn't detecting well
        self.blue_lower = np.array([90, 50, 50])
        self.blue_upper = np.array([130, 255, 255])

        ### GRID CONSTANTS
        # standard board dimensions
        self.grid_rows = 6
        self.grid_cols = 7
        self.board_state = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
        
        ### TEMPORAL SMOOTHING (PIECES)
        # prevents flickering by waiting for pieces to settle
        self.persistence_threshold = 12 
        self.detection_buffer = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
        self.current_candidate = np.zeros((self.grid_rows, self.grid_cols), dtype=int)

        ### INERTIA / MEMORY SYSTEM (BOARD)
        # remembers board location if camera view gets blocked for a bit
        self.last_matrix = None         
        self.coast_frames = 0           
        self.max_coast_frames = 90
        self.is_board_active = False 
        self.smoothed_corners = None # stores average of corner locations

        ### ADVANCED FILTERS
        # handles shadows, glints, and changing backgrounds
        self.calibration_frames = 0
        self.is_calibrated = False
        self.baseline_colors = np.zeros((self.grid_rows, self.grid_cols, 3), dtype=np.uint8) # stores RGB of empty board
        self.calibration_target_frames = 30
        self.red_fill_threshold = 0.10
        self.yellow_fill_threshold = 0.18
        self.red_min_dominance = 35
        self.yellow_min_blue_gap = 35
        self.yellow_max_rg_gap = 95
        self.empty_diff_threshold = 45
        self.top_diff_threshold = 45

        ### GAME STATE
        self.winner = 0 

    def auto_white_balance(self, img):
        """
        Simple Gray World White Balance
        Scales R, G, B channels so they average to gray
        Fixes yellow or orange tint in indoor lighting
        """
        result = img.copy()
        b, g, r = cv2.split(result)
        b_mean = np.mean(b)
        g_mean = np.mean(g)
        r_mean = np.mean(r)
        
        if b_mean == 0: b_mean = 1
        if g_mean == 0: g_mean = 1
        if r_mean == 0: r_mean = 1

        k = (b_mean + g_mean + r_mean) / 3
        
        b = cv2.multiply(b, (k / b_mean))
        g = cv2.multiply(g, (k / g_mean))
        r = cv2.multiply(r, (k / r_mean))
        
        return cv2.merge([b, g, r])

    def order_points(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def get_color_mask(self, img, color):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        if color == 'blue':
            return cv2.inRange(hsv, self.blue_lower, self.blue_upper)
        return None

    def get_board_corners(self, mask):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None, None
        
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        
        if area < 6000: 
            return None, None

        epsilon = 0.02 * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, epsilon, True)
        
        if len(approx) == 4:
            return approx.reshape(4, 2), "PolyDP"

        rect = cv2.minAreaRect(c)
        box = cv2.boxPoints(rect)
        return box, "MinAreaRect"

    def check_for_win(self):
        b = self.board_state
        rows, cols = self.grid_rows, self.grid_cols

        # Horizontal
        for r in range(rows):
            for c in range(cols - 3):
                if b[r][c] != 0 and b[r][c] == b[r][c+1] == b[r][c+2] == b[r][c+3]:
                    return b[r][c]
        # Vertical
        for r in range(rows - 3):
            for c in range(cols):
                if b[r][c] != 0 and b[r][c] == b[r+1][c] == b[r+2][c] == b[r+3][c]:
                    return b[r][c]
        # Positive Diagonal (/)
        for r in range(3, rows):
            for c in range(cols - 3):
                if b[r][c] != 0 and b[r][c] == b[r-1][c+1] == b[r-2][c+2] == b[r-3][c+3]:
                    return b[r][c]
        # Negative Diagonal (\)
        for r in range(rows - 3):
            for c in range(cols - 3):
                if b[r][c] != 0 and b[r][c] == b[r+1][c+1] == b[r+2][c+2] == b[r+3][c+3]:
                    return b[r][c]
        return 0

    def process_frame(self, frame):
        wb_frame = self.auto_white_balance(frame)

        ### FIND BOARD
        # locate blue plastic frame using color mask
        blue_mask = self.get_color_mask(wb_frame, 'blue')
        kernel = np.ones((5,5), np.uint8)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)

        pts, method = self.get_board_corners(blue_mask)
        
        warped_display = None
        current_matrix = None

        width, height = 700, 600
        dst_pts = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]], dtype="float32")

        ### MEMORY LOGIC
        # determine if have a new lock or need to rely on memory
        if pts is not None:
            rect_pts = self.order_points(pts)
            
            ### CORNER SMOOTHING (Low Pass Filter)
            # prevents grid from jittering by averaging old and new positions
            if self.smoothed_corners is None:
                self.smoothed_corners = rect_pts
            else:
                # check distance between new and old corners
                diff = np.linalg.norm(rect_pts - self.smoothed_corners)
                
                # if board moved significantly (>100px), snap immediately
                if diff > 100:
                    self.smoothed_corners = rect_pts
                else:
                    # apply smoothing with weighted average
                    # adjust alpha (0.15) to change smoothness (lower is smoother but laggier)
                    alpha = 0.15
                    self.smoothed_corners = (self.smoothed_corners * (1 - alpha)) + (rect_pts * alpha)

            current_matrix = cv2.getPerspectiveTransform(self.smoothed_corners, dst_pts)
            self.last_matrix = current_matrix
            self.coast_frames = 0
            self.is_board_active = True
            
            viz_color = (0, 255, 0) if method == "PolyDP" else (0, 255, 255)
            # draw raw detection (jittery)
            cv2.drawContours(frame, [np.int32(pts)], -1, viz_color, 2)
            # draw smoothed detection (stable)
            cv2.drawContours(frame, [np.int32(self.smoothed_corners)], -1, (255, 0, 255), 3)
            
            cv2.putText(frame, f"LOCKED ({method})", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, viz_color, 2)

        elif self.last_matrix is not None and self.coast_frames < self.max_coast_frames:
            current_matrix = self.last_matrix
            self.coast_frames += 1
            self.is_board_active = True
            cv2.putText(frame, f"COASTING ({self.max_coast_frames - self.coast_frames})", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)

        else:
            self.is_board_active = False
            self.is_calibrated = False 
            self.calibration_frames = 0
            self.smoothed_corners = None # reset smoothing on loss
            
            self.detection_buffer = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
            self.current_candidate = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
            cv2.putText(frame, "BOARD LOST - SEARCHING...", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        ### WARP AND ANALYZE
        # if board is found, flatten and check slots
        if current_matrix is not None and self.is_board_active:
            warped = cv2.warpPerspective(wb_frame, current_matrix, (width, height))
            
            ### CALIBRATION ROUTINE
            # if board is stable for 30 frames, capture empty state
            if not self.is_calibrated:
                self.calibration_frames += 1
                progress = min(100, int(self.calibration_frames / self.calibration_target_frames * 100))
                cv2.putText(frame, f"CALIBRATING... {progress}%", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                if self.calibration_frames > self.calibration_target_frames:
                    self.perform_calibration(warped)
                    self.is_calibrated = True
                    self.reset_detection_state()
            else:
                cv2.putText(frame, "CALIBRATED", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                self.analyze_grid(warped)
                self.winner = self.check_for_win()

            warped_display = warped.copy()
            self.draw_grid_debug(warped_display)

        return frame, blue_mask, warped_display

    def perform_calibration(self, warped_img):
        """ Capture average color of every slot to use as a baseline for 'Empty' """
        height, width, _ = warped_img.shape
        cell_h = height // self.grid_rows
        cell_w = width // self.grid_cols

        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                avg_color, _, _, _, _, _ = self.sample_slot(warped_img, r, c, cell_w, cell_h)
                self.baseline_colors[r, c] = avg_color

    def reset_detection_state(self):
        # Start post-calibration detection from a clean slate so
        # pre-calibration false positives do not persist as real pieces.
        self.board_state = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
        self.detection_buffer = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
        self.current_candidate = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
        self.winner = 0

    def sample_slot(self, warped_img, row, col, cell_w, cell_h):
        margin_x = int(cell_w * 0.22)
        margin_y = int(cell_h * 0.22)
        x1 = col * cell_w + margin_x
        y1 = row * cell_h + margin_y
        x2 = (col + 1) * cell_w - margin_x
        y2 = (row + 1) * cell_h - margin_y

        roi = warped_img[y1:y2, x1:x2]
        if roi.size == 0:
            empty = np.zeros(3, dtype=np.float32)
            return empty, np.zeros((1, 1, 3), dtype=np.uint8), np.zeros((1, 1), dtype=np.uint8), 0.0, 0.0, 0.0

        roi_h, roi_w = roi.shape[:2]
        mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
        radius = max(1, int(min(roi_h, roi_w) * 0.38))
        center = (roi_w // 2, roi_h // 2)
        cv2.circle(mask, center, radius, 255, -1)

        avg_color = cv2.mean(roi, mask=mask)[:3]
        avg_color = np.array(avg_color, dtype=np.float32)
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        masked_pixels = max(1, cv2.countNonZero(mask))
        red_mask1 = cv2.inRange(hsv_roi, np.array([0, 70, 70]), np.array([12, 255, 255]))
        red_mask2 = cv2.inRange(hsv_roi, np.array([165, 70, 70]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        red_mask = cv2.bitwise_and(red_mask, mask)
        red_fill = cv2.countNonZero(red_mask) / masked_pixels

        yellow_mask = cv2.inRange(hsv_roi, np.array([12, 35, 70]), np.array([48, 255, 255]))
        yellow_mask = cv2.bitwise_and(yellow_mask, mask)
        yellow_fill = cv2.countNonZero(yellow_mask) / masked_pixels

        return avg_color, hsv_roi, mask, red_fill, yellow_fill, masked_pixels

    def analyze_grid(self, warped_img):
        height, width, _ = warped_img.shape
        cell_h = height // self.grid_rows
        cell_w = width // self.grid_cols

        ### TOP ROW REFERENCE
        # grab top row colors to see if background changed
        top_row_colors = []
        for c in range(self.grid_cols):
            avg, _, _, _, _, _ = self.sample_slot(warped_img, 0, c, cell_w, cell_h)
            top_row_colors.append(avg)

        for c in range(self.grid_cols):
            # iterate rows bottom to top
            for r in range(self.grid_rows - 1, -1, -1):
                ### LATCHING LOGIC
                # if piece exists, skip it so it never disappears
                if self.board_state[r, c] != 0:
                    continue

                avg_color, hsv_roi, slot_mask, red_fill, yellow_fill, masked_pixels = self.sample_slot(
                    warped_img,
                    r,
                    c,
                    cell_w,
                    cell_h,
                )
                
                ### MEAN COLOR ANALYSIS
                # get average color of slot region
                # convert to HSV for logic
                hsv_pixel = cv2.cvtColor(np.uint8([[avg_color]]), cv2.COLOR_BGR2HSV)[0][0]
                h, s, v = int(hsv_pixel[0]), int(hsv_pixel[1]), int(hsv_pixel[2])
                b, g, red = float(avg_color[0]), float(avg_color[1]), float(avg_color[2])
                
                ### FILTER 3 GLINT DETECTION (Specular Highlights)
                # check for small cluster of bright white pixels
                # Value > 220 and Saturation < 50
                # create mask for bright white glints
                lower_white = np.array([0, 0, 220])
                upper_white = np.array([180, 50, 255])
                glint_mask = cv2.inRange(hsv_roi, lower_white, upper_white)
                glint_mask = cv2.bitwise_and(glint_mask, slot_mask)
                glint_count = cv2.countNonZero(glint_mask)
                has_glint = glint_count > 5 # if we see >5 shiny pixels it is likely plastic

                ### FILTER 4 TEXTURE / NOISE CHECK
                # calculate Standard Deviation of Value channel
                _, std_dev = cv2.meanStdDev(hsv_roi[:, :, 2], mask=slot_mask) # Index 2 is Value
                # high std_dev means high contrast or noise aka background clutter
                # low std_dev means smooth surface
                # note glints also increase std_dev so we ignore this check if has_glint is true
                is_noisy = (std_dev[0][0] > 80) and not has_glint # relaxed to 80 for yellow texture

                detected = 0 

                ### COLOR CLASSIFICATION
                red_dominance = red - max(g, b)
                yellow_blue_gap = min(red, g) - b
                yellow_rg_gap = abs(red - g)

                # check RED first
                if red_fill >= self.red_fill_threshold and red_dominance > self.red_min_dominance and s > 65:
                    detected = 1 
                
                # check YELLOW
                elif (
                    yellow_fill >= self.yellow_fill_threshold
                    and (12 <= h <= 55)
                    and (s > 35)
                    and yellow_blue_gap > self.yellow_min_blue_gap
                    and yellow_rg_gap < self.yellow_max_rg_gap
                ):
                    detected = 2 
                
                ### APPLY NO GATES (Rejection Logic)

                # Gate A is it basically same as Start-up Baseline
                if self.is_calibrated:
                    base_color = self.baseline_colors[r, c]
                    # euclidean distance between RGB vectors
                    diff_base = np.linalg.norm(avg_color - base_color)
                    if diff_base < self.empty_diff_threshold: # threshold for Same as Empty
                        detected = 0

                # Gate B is it basically same as Top Row (Dynamic Background)
                # only apply if Top Row itself isn't a piece
                top_color = top_row_colors[c]
                diff_top = np.linalg.norm(avg_color - top_color)
                # if current slot looks like empty top slot assume empty
                # but don't accidentally erase a piece if top row is also that piece color
                if diff_top < self.top_diff_threshold and not has_glint: 
                    detected = 0

                # Gate C is it too noisy (Background texture)
                if is_noisy:
                    detected = 0

                # Gate D Glint Override (The Yes Gate)
                # if strong glint and color match trust it even if other checks are borderline
                if has_glint and detected > 0:
                    pass # keep detected status
                
                ### LOGIC BUFFER
                # make sure state is consistent for a few frames
                if detected == self.current_candidate[r, c]:
                    self.detection_buffer[r, c] += 1
                else:
                    self.detection_buffer[r, c] = 0
                    self.current_candidate[r, c] = detected
                
                required_persistence = self.persistence_threshold + (6 if detected == 2 else 0)
                if self.detection_buffer[r, c] > required_persistence:
                    # gravity check
                    is_bottom = (r == self.grid_rows - 1)
                    has_support = False
                    if not is_bottom:
                         if self.board_state[r+1, c] != 0:
                             has_support = True
                    
                    if detected == 0:
                        ### ADAPTIVE LEARNING
                        # if slot is definitely empty slowly update baseline 
                        # accounts for changing backgrounds like players moving
                        if self.is_calibrated:
                            self.baseline_colors[r, c] = (self.baseline_colors[r, c] * 0.98 + avg_color * 0.02).astype(np.uint8)
                    elif is_bottom or has_support:
                        self.board_state[r, c] = detected

    def draw_grid_debug(self, img):
        height, width, _ = img.shape
        cell_h = height // self.grid_rows
        cell_w = width // self.grid_cols
        
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                cx = int(c * cell_w + cell_w/2)
                cy = int(r * cell_h + cell_h/2)
                
                state = self.board_state[r,c]
                color = (200, 200, 200) 
                if state == 1: color = (0, 0, 255) 
                if state == 2: color = (0, 255, 255) 
                
                cv2.circle(img, (cx, cy), 20, color, -1)
                cv2.rectangle(img, (c*cell_w, r*cell_h), ((c+1)*cell_w, (r+1)*cell_h), (255,0,0), 2)
        
        if self.winner != 0:
            text = "RED WINS!" if self.winner == 1 else "YELLOW WINS!"
            color = (0, 0, 255) if self.winner == 1 else (0, 255, 255)
            overlay = img.copy()
            cv2.rectangle(overlay, (0, height//2 - 60), (width, height//2 + 60), (0,0,0), -1)
            cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)
            font = cv2.FONT_HERSHEY_DUPLEX
            text_size = cv2.getTextSize(text, font, 2, 3)[0]
            text_x = (width - text_size[0]) // 2
            text_y = (height + text_size[1]) // 2
            cv2.putText(img, text, (text_x, text_y), font, 2, color, 3)

    def print_state_console(self):
        print("\n" * 50)
        print("--- CONNECT 4 STATE ---")
        print(self.board_state)
        if self.winner:
            print(f"WINNER: {'RED' if self.winner == 1 else 'YELLOW'}")

def list_available_cameras(max_check=5):
    print("Scanning for cameras...")
    available = []
    for i in range(max_check):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(i) 
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append(i)
                cap.release()
        except Exception:
            pass 
    return available

if __name__ == "__main__":
    working_cams = list_available_cameras()
    if not working_cams:
        print("No cameras found. Trying default index 0 anyway...")
        idx = 0
    elif len(working_cams) == 1:
        idx = working_cams[0]
        print(f"Auto-selecting camera {idx}")
    else:
        print(f"Cameras found: {working_cams}")
        try:
            val = input(f"Select camera index: ")
            idx = int(val)
        except:
            idx = working_cams[0]

    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    tracker = Connect4Tracker()
    print("Tracker started. Press 'q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            frame_out, mask, warped = tracker.process_frame(frame)

            cv2.imshow("Main Feed", frame_out)
            
            if warped is not None:
                cv2.imshow("Warped (WB Corrected)", warped)
                tracker.print_state_console()
            else:
                cv2.imshow("Mask", mask)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Quit key pressed.")
                break
    except KeyboardInterrupt:
        print("\nStopped by User.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
