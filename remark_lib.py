# This Python file uses the following encoding: utf-8
import sys

def non_repeating(xs):
    s = set()
    for x in xs:
        if x in s:
            return False
        else:
            s.add(x)
    return True

def ends_with(xs, ys):
    if len(xs) < len(ys):
        return False
    else:
        paired = zip(reversed(xs), reversed(ys))
        return all(map(lambda x: x[0] == x[1], paired)) 

class RemarkTree(object):
    def __init__(self, **kwargs):
        self.children = []
        self.tag = kwargs['tag'] if 'tag' in kwargs else None
        self.text = kwargs['text'] if 'text' in kwargs else None
        self.parent = kwargs['parent'] if 'parent' in kwargs else None
        self.which_child = kwargs['which_child'] if 'which_child' in kwargs else None
        self.been_unwrapped = False

    def __str__(self):
        out = ''
        if self.text is not None:
           out = out + self.text
        elif self.tag is not None:
           out = out + '[{tag}:'.format(tag=self.tag) + ''.join(map(lambda n: str(n), self.children)) + ']'
        else:
           out = out + ''.join(map(lambda n: str(n), self.children))
        return out

    def new_text_child(self, text):
        new_child = RemarkTree(text=text, parent=self, which_child=len(self.children))
        self.children.append(new_child)

    def new_remark_child(self, tag):
        new_child = RemarkTree(tag=tag, parent=self, which_child=len(self.children))
        self.children.append(new_child)
        return new_child

    def change_tag(self, new_tag):
        if self.tag is not None:
            self.tag = new_tag

    def tag_ancestry(self):
        if self.tag is None:
            return []
        tags = [self.tag]
        parent = self.parent
        while parent is not None:
            if parent.tag is not None:
                tags.append(parent.tag)
                parent = parent.parent
            else:
                break
        return list(reversed(tags))

    def is_root(self):
        return self.parent is None

    def is_last_child(self):
        if self.parent is None:
            return False
        else:
            return len(self.parent.children) - 1 == self.which_child

    def walk(self, f):
        f(self)
        for child in self.children:
            child.walk(f)

class RuleApplication(object):
    def apply(self, tree):
        pass

class UntagRuleApplication(RuleApplication):
    def __init__(self, prefix, suffix, transform):
        self.prefix = prefix
        self.suffix = suffix
        self.transform = transform

    def apply(self, tree):
        return [self.prefix, self.transform, self.suffix]

class RetagRuleApplication(RuleApplication):
    def __init__(self, new_tag):
        self.new_tag = new_tag

    def apply(self, tree):
        if tree.tag is not None:
            tree.tag = self.new_tag

class Ammendment(object):
    def __init__(self, prefix, suffix):
        self.prefix = prefix
        self.suffix = suffix 

class LiteralRule(object):
    def __init__(self):
        self.text = None
        self.replacement = None

class Rule(object):
    def __init__(self):
        self.pattern = None
        self.parents_to_target = 0
        self.application_spec = None
        self.desc = None

    def set_pattern(self, **kwargs):
        parent_tags = kwargs['tags_preceeding'] if 'tags_preceeding' in kwargs else []
        target_tag = kwargs['target_tag']
        children_tags = kwargs['tags_following'] if 'tags_following' in kwargs else []
        self.target_index = len(parent_tags)
        self.pattern = []
        self.pattern.extend(parent_tags)
        self.pattern.append(target_tag)
        self.pattern.extend(children_tags)

    def get_target(self, matched_remark):
        t = matched_remark
        for i in range(self.parents_to_target):
            t = t.parent
        return t

    # match tree against this rule, looking backward and forward as needed
    def matches(self, remark):
        backward = self.pattern[:self.target_index+1]
        forward = self.pattern[self.target_index+1:]
        if ends_with(remark.tag_ancestry(), backward):
            matching_remarks = [remark]
            for tag in forward:
                new_matching_remarks = []
                for matching_remark in matching_remarks: 
                    new_matching_remarks.extend([r for r in matching_remark.children if r.tag == tag])
                if new_matching_remarks == []:
                    return False
            #print 'rule:', self.pattern, 'matched.'
            return True

class Ruleset(object):
    def __init__(self):
        self.rules = {}
        self.rule_count = 0
        self.flattened_rules = []

    def add(self, rule):
        rank = len(rule.pattern)
        self.rule_count += 1
        if rank in self.rules:
            self.rules[rank].append(rule)
        else:
            self.rules[rank] = []
            self.rules[rank].append(rule)

    def applicable_rules(self, ancestry):
        rank = len(ancestry)
        rules = []
        for rank in range(rank, 0, -1):
            if rank in self.rules:
                rules.extend(self.rules[rank])
        return rules

    def get_rules(self):
        if len(self.flattened_rules) != self.rule_count:
            self.flattened_rules = []
            for rank in sorted(self.rules.keys(), reverse=True):
                self.flattened_rules.extend(self.rules[rank])
        return self.flattened_rules

def parse(text, out=None):
    open_count = 0
    plain_string = ''
    remark_string = ''
    if out is None:
        out = RemarkTree()
    for character in text:
        if character == '[':
            if open_count == 0:
                if len(plain_string) > 0:
                    out.new_text_child(plain_string)
                    plain_string = ''
            open_count += 1

        if open_count == 0:
            plain_string += character
        else:
           remark_string += character

        if character == ']':
            open_count -= 1
            if open_count == 0:
                tag_end = remark_string.index(':')
                tag = remark_string[1:tag_end]
                text = remark_string[tag_end+1:-1]
                parse(text, out.new_remark_child(tag))
                remark_string = ''
    if plain_string != '':
        out.new_text_child(plain_string)
    return out

class RemarkProgram(object):
    def __init__(self):
        # list of prefixes and suffixes to apply to the final string
        # these are applied in reverse
        self.everything_rules = []
        # list of textual substitutions to be done on the flattened text
        self.literal_rules = []
        # set of rules for changing tags
        self.tagging_rules = Ruleset()
        # set of rules for turning remarks into strings
        self.untagging_rules = Ruleset()

    def textual_replacement(self, **kwargs):
        try:
            rule = LiteralRule()
            rule.text = kwargs['find']
            rule.replacement = kwargs['replace']
            self.literal_rules.append(rule)
        except KeyError, e:
            print 'you done messed up', e

    def everything_rule(self, **kwargs):
        try:
            prefix = kwargs['prefix'] if 'prefix' in kwargs else None
            suffix = kwargs['suffix'] if 'suffix' in kwargs else None
            self.everything_rules.append(Ammendment(prefix, suffix))
        except KeyError, e:
            print 'you done messed up', e

    def retag_rule(self, **kwargs):
        try:
            rule = Rule()
            rule.set_pattern(**kwargs)
            rule.application_spec = RetagRuleApplication(kwargs['new_tag'])
            self.tagging_rules.add(rule)
        except KeyError, e:
            print 'you done messed up', e

    def untag_rule(self, **kwargs):
        try:
            rule = Rule()
            rule.set_pattern(**kwargs)
            prefix = kwargs['prefix'] if 'prefix' in kwargs else None
            suffix = kwargs['suffix'] if 'suffix' in kwargs else None
            transform = kwargs['transform'] if 'transform' in kwargs else (lambda x: x)
            rule.application_spec = UntagRuleApplication(prefix, suffix, transform)
            self.untagging_rules.add(rule)
        except KeyError, e:
            print 'you done messed up', e

    def rule(self, **kwargs):
        try:
            if kwargs['type'] == 'untag': self.untag_rule(**kwargs)
            elif kwargs['type'] == 'retag': self.retag_rule(**kwargs)
            elif kwargs['type'] == 'ammend': self.everything_rule(**kwargs)
            elif kwargs['type'] == 'literal': self.textual_replacement(**kwargs)
            else:
                print 'bad type of rule'
        except KeyError, e:
            print 'you done messed up', e

    def run_on_string(self, text):
        tree_history = []
        # this is a dumb hack because python doesn't have 
        # proper closures 
        tree_string = {0:''} 
        tree = parse(text)

        def apply_tag_rules(tree):
            if tree.tag is not None:
                tree_string[0] = tree_string[0] + tree.tag
            tree_string[0] = tree_string[0] + ':'
            for rule in self.tagging_rules.get_rules():
                if rule.matches(tree):
                    rule.application_spec.apply(tree)

        flattened = []
        def apply_untag_rules(tree):
            if tree.been_unwrapped:
                return
            if tree.text is not None:
                flattened.append(tree.text)
            elif tree.tag is not None:
                for rule in self.untagging_rules.get_rules():
                    if rule.matches(tree):
                        prefix, transform, suffix = rule.application_spec.apply(tree)
                        if prefix is not None:
                            flattened.append(prefix)
                        mark = len(flattened)
                        for child in tree.children:
                            apply_untag_rules(child)
                        result = transform(''.join(flattened[mark:]))
                        del flattened[mark:]
                        flattened.append(result)
                        if suffix is not None:
                            flattened.append(suffix)
                        break
            else:
                for child in tree.children:
                    apply_untag_rules(child)

        def apply_literal_rules(str):
            for rule in self.literal_rules:
                str = str.replace(rule.text, rule.replacement)
            return str

        def apply_everything_rules(str):
            for rule in reversed(self.everything_rules):
                if rule.prefix is not None:
                    str = rule.prefix + str
                if rule.suffix is not None:
                    str = str + rule.suffix
            return str

        # this repeats more than it should
        ##print tree
        ##print '--------------------------'
        while non_repeating(tree_history):
            tree.walk(apply_tag_rules)
            ##print tree
            ##print '--------------------------'
            tree_history.append(tree_string[0])
            tree_string[0] = ''

        apply_untag_rules(tree)
        flattened = ''.join(flattened)

        replaced = apply_literal_rules(flattened)
        ammended = apply_everything_rules(replaced)
        return ammended
    
    def run(self):
        print self.run_on_string(''.join(sys.stdin))
