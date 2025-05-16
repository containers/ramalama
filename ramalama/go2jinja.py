#
# Copied from https://github.com/engelmi/go2jinja
#

import argparse
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class NodeType(Enum):
    RANGE = "range"
    CONTINUE = "continue"
    BREAK = "break"
    IF = "if"
    ELIF = "else if"
    ELSE = "else"
    END = "end"
    CONTENT = ""
    STATEMENT = "stmt"
    ASSIGNMENT = "assignment"


@dataclass
class Node:
    start: int
    end: int
    content: str

    type: NodeType

    prev: Optional["Node"]
    next: Optional["Node"]
    parent: Optional["Node"]

    open_scope_node: Optional["Node"] = None
    end_scope_node: Optional["Node"] = None
    children: list["Node"] = field(default_factory=lambda: [])

    artificial: bool = False


class FunctionType(Enum):
    PLAIN = "plain"

    AND = "and"
    OR = "or"
    NOT = "not"

    EQUALS = "eq"
    NEQUALS = "neq"
    LESSER = "lt"
    LESSEREQUALS = "le"
    GREATER = "gt"
    GREATEREQUALS = "ge"

    LEN = "len"
    SLICE = "slice"
    INDEX = "index"

    PRINTF = "printf"


FUNCTION_MAPPING = {
    FunctionType.AND: "and",
    FunctionType.OR: "or",
    FunctionType.NOT: "not",
    FunctionType.EQUALS: "==",
    FunctionType.NEQUALS: "!=",
    FunctionType.LESSER: "<",
    FunctionType.LESSEREQUALS: "<=",
    FunctionType.GREATER: ">",
    FunctionType.GREATEREQUALS: ">=",
    FunctionType.LEN: "|length",
    FunctionType.SLICE: "",
    FunctionType.INDEX: "",
    FunctionType.PRINTF: "printf",
}


@dataclass
class FunctionNode:
    content: str
    type: FunctionType

    operands: list["FunctionNode"] = field(default_factory=lambda: [])

    def to_jinja(self) -> str:
        if self.type in [
            FunctionType.EQUALS,
            FunctionType.NEQUALS,
            FunctionType.GREATER,
            FunctionType.GREATEREQUALS,
            FunctionType.LESSER,
            FunctionType.LESSEREQUALS,
        ]:
            return " or ".join(
                [
                    f"{self.operands[0].to_jinja()}{FUNCTION_MAPPING[self.type]}{self.operands[i].to_jinja()}"
                    for i in range(1, len(self.operands))
                ]
            )
        elif self.type in [FunctionType.AND, FunctionType.OR]:
            return f" {FUNCTION_MAPPING[self.type]} ".join([op.to_jinja() for op in self.operands])
        elif self.type == FunctionType.NOT:
            return f"{FUNCTION_MAPPING[self.type]} {self.operands[0].to_jinja()}"
        elif self.type == FunctionType.LEN:
            return f"({self.operands[0].to_jinja()}){FUNCTION_MAPPING[self.type]}"
        elif self.type == FunctionType.SLICE:
            s = ":"
            if len(self.operands) == 2:
                s = f"{self.operands[1].to_jinja()}:"
            elif len(self.operands) > 2:
                s = ":".join(self.operands[i].to_jinja() for i in range(1, len(self.operands)))
            return f"({self.operands[0].to_jinja()})[{s}]"
        elif self.type == FunctionType.INDEX:
            return f"({self.operands[0].to_jinja()})[{self.operands[1].to_jinja()}]"
        elif self.type == FunctionType.PRINTF:
            return f"{self.operands[0].to_jinja()}.format({', '.join([op.to_jinja() for op in self.operands[1:]])})"

        if self.content.startswith('"') and self.content.endswith('"'):
            return self.content.replace("\n", "\\n")
        return self.content


GO_SYMBOL_OPEN_BRACKETS = "{{"
GO_SYMBOL_CLOSE_BRACKETS = "}}"
JINJA_SYMBOL_OPEN_BRACKETS = "{%"
JINJA_SYMBOL_CLOSE_BRACKETS = "%}"
JINJA_SYMBOL_STMT_OPEN_BRACKETS = "{{"
JINJA_SYMBOL_STMT_CLOSE_BRACKETS = "}}"
SYMBOL_REMOVE_WHITESPACE = "-"

REGEX_VARIABLE = "(\\.[A-Za-z_][A-Za-z0-9_]*)"
REGEX_LOCAL_VARIABLE = "(\\$\\.?[A-Za-z_][A-Za-z0-9_]*)"
REGEX_NODE_START_BLOCK = f"{GO_SYMBOL_OPEN_BRACKETS}{SYMBOL_REMOVE_WHITESPACE}?\\s*"
REGEX_NODE_PIPELINE = "(.+\\n*)"
REGEX_NODE_END_BLOCK = f"\\s*{SYMBOL_REMOVE_WHITESPACE}?{GO_SYMBOL_CLOSE_BRACKETS}"
REGEX_NODE_IF = f"{REGEX_NODE_START_BLOCK}(if)\\s{REGEX_NODE_PIPELINE}{REGEX_NODE_END_BLOCK}"
REGEX_NODE_ELIF = f"{REGEX_NODE_START_BLOCK}(else if)\\s{REGEX_NODE_PIPELINE}{REGEX_NODE_END_BLOCK}"
REGEX_NODE_ELSE = f"{REGEX_NODE_START_BLOCK}(else){REGEX_NODE_END_BLOCK}"
REGEX_NODE_END = f"{REGEX_NODE_START_BLOCK}(end){REGEX_NODE_END_BLOCK}"
REGEX_NODE_RANGE = (
    f"{REGEX_NODE_START_BLOCK}(range)\\s+"
    f"({REGEX_LOCAL_VARIABLE}\\s*,\\s*{REGEX_LOCAL_VARIABLE}\\s*:=\\s*)"
    f"?{REGEX_VARIABLE}{REGEX_NODE_END_BLOCK}"
)
REGEX_NODE_CONTINUE = f"{REGEX_NODE_START_BLOCK}continue{REGEX_NODE_END_BLOCK}"  # noqa: E275
REGEX_NODE_BREAK = f"{REGEX_NODE_START_BLOCK}break{REGEX_NODE_END_BLOCK}"  # noqa: E275
REGEX_NODE_STMT = f"{REGEX_NODE_START_BLOCK}({REGEX_VARIABLE}|{REGEX_LOCAL_VARIABLE}){REGEX_NODE_END_BLOCK}"
REGEX_NODE_ASSIGNMENT = (
    f"{REGEX_NODE_START_BLOCK}{REGEX_LOCAL_VARIABLE}\\s*:?=\\s*{REGEX_NODE_PIPELINE}{REGEX_NODE_END_BLOCK}"
)
GO_KEYWORDS: Dict[NodeType, re.Pattern] = {
    NodeType.IF: re.compile(R"{}".format(REGEX_NODE_IF), re.S),
    NodeType.ELIF: re.compile(R"{}".format(REGEX_NODE_ELIF), re.S),
    NodeType.ELSE: re.compile(R"{}".format(REGEX_NODE_ELSE), re.S),
    NodeType.END: re.compile(R"{}".format(REGEX_NODE_END), re.S),
    NodeType.RANGE: re.compile(R"{}".format(REGEX_NODE_RANGE), re.S),
    NodeType.STATEMENT: re.compile(R"{}".format(REGEX_NODE_STMT), re.S),
    NodeType.ASSIGNMENT: re.compile(R"{}".format(REGEX_NODE_ASSIGNMENT), re.S),
    NodeType.CONTINUE: re.compile(R"{}".format(REGEX_NODE_CONTINUE), re.S),
    NodeType.BREAK: re.compile(R"{}".format(REGEX_NODE_BREAK), re.S),
}


def detect_node_type(stmt: str) -> Optional[NodeType]:
    # from most complex to least
    ordered_regex_list = [
        (NodeType.RANGE, GO_KEYWORDS[NodeType.RANGE]),
        (NodeType.IF, GO_KEYWORDS[NodeType.IF]),
        (NodeType.ELIF, GO_KEYWORDS[NodeType.ELIF]),
        (NodeType.ELSE, GO_KEYWORDS[NodeType.ELSE]),
        (NodeType.END, GO_KEYWORDS[NodeType.END]),
        (NodeType.CONTINUE, GO_KEYWORDS[NodeType.CONTINUE]),
        (NodeType.BREAK, GO_KEYWORDS[NodeType.BREAK]),
        (NodeType.ASSIGNMENT, GO_KEYWORDS[NodeType.ASSIGNMENT]),
        (NodeType.STATEMENT, GO_KEYWORDS[NodeType.STATEMENT]),
    ]

    for regex in ordered_regex_list:
        ntype, reg = regex
        if reg.match(stmt) is not None:
            return ntype
    return None


def parse_go_template(content: str) -> list[Node]:
    root_nodes: list[Node] = []

    prev_expr_node: Node = None
    current_scope_nodes: list[Node] = []
    start_pos = content.find(GO_SYMBOL_OPEN_BRACKETS)
    end_pos = 0
    while start_pos != -1:
        if end_pos == 0 and start_pos != 0:
            content_node = Node(
                end_pos,
                start_pos,
                content[end_pos:start_pos],
                NodeType.CONTENT,
                prev=None,
                next=None,
                parent=None,
                children=[],
                artificial=False,
            )
            root_nodes.append(content_node)
        elif start_pos - end_pos > 0:
            content_node = Node(
                end_pos,
                start_pos,
                content[end_pos:start_pos],
                NodeType.CONTENT,
                prev=None,
                next=None,
                parent=None,
                children=[],
                artificial=False,
            )
            current_scope_node = None if not current_scope_nodes else current_scope_nodes[-1]
            if current_scope_node is not None:
                content_node.parent = current_scope_node
                current_scope_node.children.append(content_node)
            else:
                root_nodes.append(content_node)

        end_pos = content.find(GO_SYMBOL_CLOSE_BRACKETS, start_pos) + len(GO_SYMBOL_CLOSE_BRACKETS)
        if end_pos == -1:
            raise IndexError("Found opening without closing brackets")

        stmt = content[start_pos:end_pos]
        node_type = detect_node_type(stmt)

        expr_node = Node(
            start_pos,
            end_pos,
            content[start_pos:end_pos],
            node_type,
            prev=prev_expr_node,
            next=None,
            parent=None,
            children=[],
            artificial=False,
        )
        if prev_expr_node is not None:
            prev_expr_node.next = expr_node

        if expr_node.type in [NodeType.IF, NodeType.RANGE]:
            current_scope_node = None if not current_scope_nodes else current_scope_nodes[-1]
            if current_scope_node is not None:
                expr_node.parent = current_scope_node
            current_scope_nodes.append(expr_node)
        elif expr_node.type in [NodeType.ELIF, NodeType.ELSE]:
            if current_scope_nodes:
                prev = current_scope_nodes.pop()
                prev.end_scope_node = expr_node
                expr_node.open_scope_node = prev
            current_scope_node = None if not current_scope_nodes else current_scope_nodes[-1]
            if current_scope_node is not None:
                expr_node.parent = current_scope_node
            current_scope_nodes.append(expr_node)
        elif expr_node.type == NodeType.END:
            prev = current_scope_nodes.pop()
            prev.end_scope_node = expr_node
            expr_node.open_scope_node = prev
            current_scope_node = None if not current_scope_nodes else current_scope_nodes[-1]
            if current_scope_node is not None:
                expr_node.parent = current_scope_node
        else:
            current_scope_node = None if not current_scope_nodes else current_scope_nodes[-1]
            if current_scope_node is not None:
                expr_node.parent = current_scope_node

        if expr_node.parent is None:
            root_nodes.append(expr_node)
        else:
            expr_node.parent.children.append(expr_node)

        prev_expr_node = expr_node

        start_pos = content.find(GO_SYMBOL_OPEN_BRACKETS, end_pos)

    if end_pos < len(content):
        content_node = Node(
            end_pos,
            len(content) + 1,
            content[end_pos : len(content) + 1],
            NodeType.CONTENT,
            prev=None,
            next=None,
            parent=None,
            children=[],
            artificial=False,
        )
        root_nodes.append(content_node)

    return root_nodes


def translate_continue_nodes(root_nodes: list[Node]) -> list[Node]:
    continue_nodes: list[Node] = []

    def find_continue_nodes(nodes: list[Node]):
        for node in nodes:
            if node.type == NodeType.CONTINUE:
                continue_nodes.append(node)
            find_continue_nodes(node.children)

    def add_if_continue_check_block(parent_node: Node, start_index: int) -> None:
        to_wrap = parent_node.children[start_index:]
        if not to_wrap:
            return

        if_node = Node(
            -1,
            -1,
            (
                f"{GO_SYMBOL_OPEN_BRACKETS} {NodeType.IF.value} {FunctionType.NEQUALS.value} {skip_variable} 1 "
                f"{GO_SYMBOL_CLOSE_BRACKETS}"
            ),
            NodeType.IF,
            prev=to_wrap[0].prev,
            next=to_wrap[0],
            parent=parent_node,
            children=to_wrap,
            artificial=True,
        )
        end_node = Node(
            -1,
            -1,
            f"{GO_SYMBOL_OPEN_BRACKETS} {NodeType.END.value} {GO_SYMBOL_CLOSE_BRACKETS}",
            NodeType.END,
            prev=to_wrap[-1],
            next=to_wrap[-1].next,
            parent=if_node,
            children=[],
            artificial=True,
        )

        if_node.end_scope_node = end_node
        end_node.open_scope_node = if_node

        to_wrap[0].prev = if_node
        for elem in to_wrap:
            elem.parent = if_node
        to_wrap[-1].next = end_node

        parent_node.children = parent_node.children[:start_index] + [if_node, end_node]

    find_continue_nodes(root_nodes)

    skip_variable = "$should_continue"
    for continue_node in continue_nodes:
        # find start of loop to initialize continue skip variable
        #   and add if-end nodes for skipping
        should_break = False
        for_node = continue_node.parent
        while for_node is not None and not should_break:
            if for_node.type == NodeType.RANGE:
                initial_set_node = Node(
                    -1,
                    -1,
                    (
                        f"{GO_SYMBOL_OPEN_BRACKETS}{SYMBOL_REMOVE_WHITESPACE} {skip_variable} := 0"
                        f"{SYMBOL_REMOVE_WHITESPACE}{GO_SYMBOL_CLOSE_BRACKETS}"
                    ),
                    NodeType.ASSIGNMENT,
                    prev=for_node,
                    next=for_node.next,
                    parent=for_node,
                    children=[],
                    artificial=True,
                )
                for_node.next.prev = initial_set_node
                for_node.next = initial_set_node
                for_node.children = [initial_set_node] + for_node.children
                should_break = True

            start_index = 0
            for child in for_node.children:
                if child.start > continue_node.start and child.type not in [
                    NodeType.ELIF,
                    NodeType.END,
                ]:
                    continue
                start_index += 1
            add_if_continue_check_block(for_node, start_index)

            for_node = for_node.parent

        # transform continue node to assignment node
        continue_node.type = NodeType.ASSIGNMENT
        continue_node.start = -1
        continue_node.end = -1
        remove_whitespace_open = (
            SYMBOL_REMOVE_WHITESPACE
            if continue_node.content[len(GO_SYMBOL_OPEN_BRACKETS) + 1] == SYMBOL_REMOVE_WHITESPACE
            else ""
        )
        remove_whitespace_close = (
            SYMBOL_REMOVE_WHITESPACE
            if continue_node.content[(len(GO_SYMBOL_CLOSE_BRACKETS) + 1) * -1] == SYMBOL_REMOVE_WHITESPACE
            else ""
        )
        continue_node.content = (
            f"{GO_SYMBOL_OPEN_BRACKETS}"
            f"{remove_whitespace_open}{skip_variable} := 1 "
            f"{remove_whitespace_close}{GO_SYMBOL_CLOSE_BRACKETS}"
        )
        continue_node.artificial = True

    return root_nodes


def is_jinja_template(content: str) -> bool:
    return re.compile(R".*{%\-?.+\-?%}", re.S).match(content) is not None


def is_go_template(content: str) -> bool:
    return re.compile(R".*{{\-?.+\-?}}", re.S).match(content) is not None and not is_jinja_template(content)


def go_to_jinja(content: str) -> str:
    if not is_go_template(content):
        return ""

    loop_vars = []
    loop_index_vars = []

    def transform_go_var_to_jinja(var: str, check_loop_vars: bool = True) -> str:
        var = var.replace(".", "").lower()
        if check_loop_vars and loop_vars:
            var = f'{loop_vars[-1]}["{var}"]'
        return var

    def transform_go_local_var_to_jinja(var: str) -> str:
        if loop_index_vars and loop_index_vars[-1] == var:
            return "loop.index0"
        return transform_go_var_to_jinja(var, False).replace("$", "").lower()

    def parse_pipeline(pipeline: str) -> str:
        def parse_variable(pipeline: str) -> str:
            reg = re.compile(R"{}".format(f"{REGEX_VARIABLE}"))
            m = reg.match(pipeline)
            if m is not None:
                start, end = m.span()
                if start == 0 and end == (len(pipeline)):
                    return transform_go_var_to_jinja(pipeline)

            reg = re.compile(R"{}".format(f"{REGEX_LOCAL_VARIABLE}"))
            m = reg.match(pipeline)
            if m is not None:
                start, end = m.span()
                if start == 0 and end == (len(pipeline)):
                    return transform_go_local_var_to_jinja(pipeline)

            return pipeline

        def parse_functions(pipeline: str) -> FunctionNode:
            if not pipeline.isspace():
                pipeline = pipeline.lstrip().rstrip()

            longest_match: FunctionType = None
            for ft in FUNCTION_MAPPING.keys():
                if pipeline.startswith(ft.value):
                    if longest_match is None or len(ft.value) > len(longest_match.value):
                        longest_match = ft

            if longest_match is not None:
                func_content = pipeline[len(longest_match.value) :].strip()
                node = FunctionNode(func_content, longest_match)

                quotes_open = False
                open_brackets = 0
                groups = []
                start, end = 0, 0
                i = 0
                prev_c = ""
                for c in func_content:
                    if c == "(" and not quotes_open:
                        if open_brackets == 0:
                            start = i
                        open_brackets += 1
                    elif c == ")" and not quotes_open:
                        open_brackets -= 1
                        if open_brackets == 0:
                            end = i
                            groups.append(func_content[start + 1 : end])
                    elif c == '"' and prev_c != "\\":
                        quotes_open = not quotes_open
                    elif c == " " and not quotes_open and open_brackets == 0 and prev_c != ")":
                        end = i
                        groups.append(func_content[start:end])
                        start = i + 1

                    prev_c = c
                    i += 1

                    if i == len(func_content):
                        rest = func_content[end:].lstrip(" )")
                        if rest != "":
                            groups.append(rest)

                for group in groups:
                    node.operands.append(parse_functions(group))

                return node

            return FunctionNode(parse_variable(pipeline), FunctionType.PLAIN)

        return parse_functions(pipeline).to_jinja()

    def node_to_jinja_str(node: Node) -> str:
        if node.type == NodeType.STATEMENT:
            m = GO_KEYWORDS[NodeType.STATEMENT].match(node.content)
            if m is not None:
                content = transform_go_var_to_jinja(node.content[m.start(1) : m.end(1)])
                content = transform_go_local_var_to_jinja(content)
                content = node.content[: m.start(1)] + content + node.content[m.end(1) :]
                return content.replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_STMT_OPEN_BRACKETS).replace(
                    GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_STMT_CLOSE_BRACKETS
                )
        elif node.type == NodeType.IF:
            m = GO_KEYWORDS[NodeType.IF].match(node.content)
            if m is not None and len(m.groups()) == 2:
                pipeline = m.groups()[1].strip()
                return (
                    node.content.replace(pipeline, parse_pipeline(pipeline))
                    .replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS)
                    .replace(GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS)
                )
        elif node.type == NodeType.ELIF:
            m = GO_KEYWORDS[NodeType.ELIF].match(node.content)
            if m is not None and len(m.groups()) == 2:
                pipeline = m.groups()[1].strip()
                return (
                    node.content.replace(pipeline, parse_pipeline(pipeline))
                    .replace(node.type.value, "elif")
                    .replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS)
                    .replace(GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS)
                )
        elif node.type == NodeType.ELSE:
            return node.content.replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS).replace(
                GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS
            )
        elif node.type == NodeType.END:
            m = GO_KEYWORDS[NodeType.END].match(node.content)
            if m is None:
                return ""

            if node.open_scope_node.type in [NodeType.IF, NodeType.ELIF, NodeType.ELSE]:
                return (
                    node.content[: m.start(1)].replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS)
                    + "endif"
                    + node.content[m.end(1) :].replace(GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS)
                )
            elif node.open_scope_node.type == NodeType.RANGE:
                loop_vars.pop()
                if loop_index_vars:
                    loop_index_vars.pop()

                return (
                    node.content[: m.start(1)].replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS)
                    + "endfor"
                    + node.content[m.end(1) :].replace(GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS)
                )
        elif node.type == NodeType.ASSIGNMENT:
            m = GO_KEYWORDS[NodeType.ASSIGNMENT].match(node.content)
            if m is not None and len(m.groups()) == 2:
                variable = m.groups()[0].strip()
                pipeline = m.groups()[1].strip()
                return (
                    node.content.replace(variable, f"set {transform_go_local_var_to_jinja(variable)}", 1)
                    .replace(pipeline, parse_pipeline(pipeline), 1)
                    .replace(":=", "=", 1)
                    .replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS, 1)
                    .replace(GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS, 1)
                )
        elif node.type == NodeType.RANGE:
            m = GO_KEYWORDS[NodeType.RANGE].match(node.content)
            if m is not None:
                loop_var = transform_go_var_to_jinja(m.groups()[4])
                loop_vars.append(loop_var[0])
                if m.groups()[2] is not None:
                    loop_index_vars.append(m.groups()[2])
                content = (
                    node.content.replace("range", f"for {loop_var[0]} in")
                    .replace(m.groups()[4], transform_go_var_to_jinja(m.groups()[4], False))
                    .replace(GO_SYMBOL_OPEN_BRACKETS, JINJA_SYMBOL_OPEN_BRACKETS)
                    .replace(GO_SYMBOL_CLOSE_BRACKETS, JINJA_SYMBOL_CLOSE_BRACKETS)
                )
                if m.groups()[1] is not None:
                    content = content.replace(m.groups()[1], "")
                return content

        return node.content

    def nodes_to_jinja_str(nodes: list[Node]) -> str:
        res = ""
        for node in nodes:
            res += node_to_jinja_str(node)
            res += nodes_to_jinja_str(node.children)
        return res

    return nodes_to_jinja_str(translate_continue_nodes(parse_go_template(content)))


def tree_structure(nodes: list[Node], level: int) -> str:
    res = ""
    for node in nodes:
        parent_type = "--" if node.parent is None else node.parent.type
        res += level * "\t" + f"{node.type}: {node.start},{node.end} - {parent_type} - {node.content}\n"
        res += tree_structure(node.children, level + 1)

    return res


def tree_content(nodes: list[Node], level: int) -> str:
    res = ""
    for node in nodes:
        res += node.content
        res += tree_content(node.children, level + 1)
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="go2jinja",
        description="Simple Tool for converting Go Templates to Jinja Templates",
    )

    parser.add_argument(
        "--go-template",
        dest="template",
        required=True,
        help="Path to the file containing the Go Template to convert to Jinja",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default="",
        help="Output file path for the converted Jinja Template. If empty, prints to stdout.",
    )

    args = parser.parse_args()

    jinja = ""
    with open(args.template, "r") as input:
        jinja = go_to_jinja(input.read())
    if args.output == "":
        print(jinja)
        sys.exit(0)
    with open(args.output, "w") as output:
        output.write(jinja)
        output.flush()
