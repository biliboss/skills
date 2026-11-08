// Return only Command's current state or its next change. No key events are captured.
#include <ApplicationServices/ApplicationServices.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    int previous = argc > 1 ? atoi(argv[1]) : -1;
    int held = 0;
    // Bounded below Herdr exec's 30-second limit; no detached watcher.
    for (int tick = 0; tick < 600; tick++) {
        held = (CGEventSourceFlagsState(kCGEventSourceStateCombinedSessionState) & kCGEventFlagMaskCommand) != 0;
        if (held != previous) break;
        usleep(30000);
    }
    printf("%d\n", held);
    return 0;
}
