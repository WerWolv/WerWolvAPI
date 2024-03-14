import re

class crash_log:

    def __init__(self, log_content: str):
        self.log_content = log_content
        self.log_lines = log_content.split('\n')
        self.log_lines = [x.strip() for x in self.log_lines]

    def parse(self):
        # parse the log, lines are formatted like this:
        # [2021-01-01] [INFO] [main] Parsing crash file: /path/to/crash/file
        # we can cut every line by it's last `]` that has a non-number character before it
        # collect all the ']' characters in each line
        self.log_lines = [re.split(r'\D\]', x)[-1].strip() for x in self.log_lines]
        # remove empty lines
        self.log_lines = [x for x in self.log_lines if x]

        # first line is 'Welcome to ImHex <version>!'
        self.version = self.log_lines[0].split(' ')[-1].replace('!', '')
        # second line is the commit hash 'Compiled using commit <branch>@<hash>'
        self.commit = self.log_lines[1].split(' ')[-1]
        # third line shows the Os and architecture 'Running on <os identifer ( can be longer than one word )>', we can just omit the first two words
        self.os = ' '.join(self.log_lines[2].split(' ')[2:])
        # fitfh line is the gpu 'Using: '<gpu name>' GPU'
        self.gpu = self.log_lines[4].split(' ')[1].replace('\'', '')
        # after that any amount of arbitrary log lines come, until the line 'Wrote crash.json file to <path>'
        # above that line is the crash reason.

        # find the words 'Wrote crash.json file to' and get the path
        crash_line = 0
        for i, line in enumerate(self.log_lines):
            if 'Wrote crash.json file to' in line:
                crash_line = i
                break

        # get crash reason
        self.crash_reason = self.log_lines[crash_line - 1]

        # after crash line follows the stack trace
        self.stack_trace = self.log_lines[crash_line + 1:]

        # the stack trace ends when lines like 'Exit task' or 'Aborted' appear
        # we can just cut the stack trace at the first line that contains 'Exit task' or 'Aborted'
        for i, line in enumerate(self.stack_trace):
            if 'Exit task' in line or 'Aborted' in line:
                self.stack_trace = self.stack_trace[:i]
                break

        if len(self.stack_trace) < 3:
            self.valid = False
            return

        # find the relevant stack trace lines

        # for windows the crash handler begins after a call to `RtlRaiseException` or `KiUserExceptionDispatcher`
        # for linux the crash handler begins after a call to either 'hex::crash::handleCrash' or 'hex::crash::setupCrashHandler'
        # due to the symbols being mangled we search for 'hex' 'crash' 'handleCrash' and 'setupCrashHandler' in the stack trace line

        # find the first line that contains any of the keywords

        # we want to travse the stack trace from the bottom to the top
        traverse_stack_trace = self.stack_trace[::-1]
        crash_handler_line = -1
        for i, line in enumerate(traverse_stack_trace):
            if any(x in line for x in ['RtlRaiseException', 'KiUserExceptionDispatcher']): # windows signal handler
                crash_handler_line = i
                break
            if any(x in line for x in ['abort', 'exit']): # a abort singal (either exception or assertion)
                crash_handler_line = i
                break
            if any(x in line for x in ['signal']): # the signal handler from imhex (first entry we can find)
                crash_handler_line = i
                break
            if any(x in line for x in ['hex', 'crash', 'handleCrash', 'setupCrashHandler']): # if we can't find any prior indicator, try the crash handler function
                # check if `hex` and `crash` are in the same line
                if 'hex' in line and 'crash' in line:
                    crash_handler_line = i
                    break

        if crash_handler_line == -1:
            self.valid = False
            return
        
        # translate line number to the original stack trace
        crash_handler_line = len(traverse_stack_trace) - crash_handler_line
        # increase the line number by 1 to get the first relevant line
        crash_handler_line += 1

        # cut the handler section and only keep 5 relevant lines after the handler
        self.relevant_stack_trace = self.stack_trace[crash_handler_line:crash_handler_line + 5]
        pass

    def build_embed(self):
        # build embed json
        relevant_lines = '\n'.join(self.relevant_stack_trace)
        embed = {
            "embeds": [
                {
                    "type": "rich",
                    "title": "Crash Report",
                    "description": "A crash report has been detected.",
                    "color": 0x0000FF,
                    "fields": [
                        {
                            "name": "Info",
                            "value": f"Version: {self.version}\nCommit: {self.commit}",
                        },
                        { 
                            "name": "OS",
                            "value": f"Type: {self.os}\nGPU: {self.gpu}"
                        },
                        {
                            "name": "Crash",
                            "value": f"Reason: {self.crash_reason}\n\n```{relevant_lines}```"
                        }
                    ]
                }
            ]
        }

        return embed


if __name__ == '__main__':
    with open('crash.log', 'r') as f:
        log = crash_log(f.read())
        log.parse()

        import requests
        import json
        import config

        data = log.build_embed()

        form_data = {
            'payload_json': (None, json.dumps(data), 'application/json'),
            'files[0]': ('crash.log', open('crash.log', 'rb'))
        }

        res = requests.post(config.ImHexApi.CRASH_WEBHOOK, files = form_data)
        
        print(json.dumps(log.build_embed(), indent = 4))
        print(res.text)
        pass