// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice E31 read-only creation-call fixture. Constructor returns data rather
/// than runtime code; public runs use eth_call with no `to` and never deploy.
contract LifecycleProbe {
    error UnknownCase();

    constructor(uint256 mode, uint256 arg) payable {
        if (mode == 0) {
            // Child init returns arg bytes of zero-filled runtime code.
            bytes memory init = abi.encodePacked(hex"61", bytes2(uint16(arg)), hex"6000f3");
            uint256 beforeGas = gasleft();
            address child;
            assembly { child := create(0, add(init, 32), mload(init)) }
            uint256 spent = beforeGas - gasleft();
            uint256 codeSize;
            bytes32 codeHash;
            assembly {
                codeSize := extcodesize(child)
                codeHash := extcodehash(child)
            }
            uint256[] memory words = new uint256[](4);
            words[0] = uint256(uint160(child));
            words[1] = codeSize;
            words[2] = uint256(codeHash);
            words[3] = spent;
            emitWords(words);
        } else if (mode == 1) {
            // STOP-only child init; allocate and expand memory before timing.
            bytes memory init = new bytes(arg);
            uint256 beforeGas = gasleft();
            address child;
            assembly { child := create(0, add(init, 32), mload(init)) }
            uint256 spent = beforeGas - gasleft();
            uint256[] memory words = new uint256[](3);
            words[0] = uint256(uint160(child));
            words[1] = child.code.length;
            words[2] = spent;
            emitWords(words);
        } else if (mode == 2) {
            Payload child = new Payload();
            (bool returned, bytes memory output) = address(child).call(hex"00");
            (bool reverted, bytes memory revertData) = address(child).call(hex"01");
            uint256 returnWord;
            uint256 revertWord;
            assembly {
                returnWord := shr(224, mload(add(output, 32)))
                revertWord := shr(224, mload(add(revertData, 32)))
            }
            uint256[] memory words = new uint256[](7);
            words[0] = uint256(uint160(address(child)));
            words[1] = returned ? 1 : 0;
            words[2] = output.length;
            words[3] = returnWord;
            words[4] = reverted ? 1 : 0;
            words[5] = revertData.length;
            words[6] = revertWord;
            emitWords(words);
        } else if (mode == 3) {
            // REVERT returns unused gas while still failing inner CREATE.
            bytes memory bad = hex"60006000fd";
            bytes memory good = hex"00";
            address failed;
            address succeeded;
            assembly {
                failed := create(0, add(bad, 32), mload(bad))
                succeeded := create(0, add(good, 32), mload(good))
            }
            uint256[] memory words = new uint256[](3);
            words[0] = uint256(uint160(address(this)));
            words[1] = uint256(uint160(failed));
            words[2] = uint256(uint160(succeeded));
            emitWords(words);
        } else if (mode == 4) {
            // arg=0 needs no funds; arg=1 uses a funded sender's one wei.
            Destroyer child = new Destroyer{value: arg}();
            address payable beneficiary = payable(address(0x000000000000000000000000000000000000dEaD));
            uint256 beforeCode = address(child).code.length;
            bytes32 beforeHash = address(child).codehash;
            uint256 beforeBalance = address(child).balance;
            uint256 beneficiaryBefore = beneficiary.balance;
            (bool killed,) = address(child).call(abi.encodeWithSelector(Destroyer.kill.selector, beneficiary));
            uint256[] memory words = new uint256[](10);
            words[0] = uint256(uint160(address(child)));
            words[1] = beforeCode;
            words[2] = uint256(beforeHash);
            words[3] = beforeBalance;
            words[4] = beneficiaryBefore;
            words[5] = killed ? 1 : 0;
            words[6] = address(child).code.length;
            words[7] = uint256(address(child).codehash);
            words[8] = address(child).balance;
            words[9] = beneficiary.balance;
            emitWords(words);
        } else if (mode == 5) {
            uint256 beforeBalance = address(4).balance;
            uint256 callerBefore = address(this).balance;
            (bool ok, bytes memory output) = address(4).call{value: 1}(hex"5a");
            uint256 firstByte = output.length == 0 ? 0 : uint8(output[0]);
            uint256[] memory words = new uint256[](6);
            words[0] = ok ? 1 : 0;
            words[1] = output.length;
            words[2] = firstByte;
            words[3] = beforeBalance;
            words[4] = address(4).balance;
            words[5] = callerBefore - address(this).balance;
            emitWords(words);
        } else if (mode == 6) {
            Depth child = new Depth();
            uint256 beforeGas = gasleft();
            (bool ok, bytes memory output) = address(child).call(abi.encode(arg, uint256(0)));
            uint256 spent = beforeGas - gasleft();
            uint256 reached;
            uint256 depth;
            if (output.length == 64) {
                assembly {
                    depth := mload(add(output, 32))
                    reached := mload(add(output, 64))
                }
            }
            uint256[] memory words = new uint256[](5);
            words[0] = uint256(uint160(address(child)));
            words[1] = ok ? 1 : 0;
            words[2] = depth;
            words[3] = reached;
            words[4] = spent;
            emitWords(words);
        } else {
            revert UnknownCase();
        }
    }

    function emitWords(uint256[] memory words) private pure {
        assembly { return(add(words, 32), mul(mload(words), 32)) }
    }
}

contract Payload {
    fallback() external {
        assembly {
            mstore(0, shl(224, 0xdeadbeef))
            switch byte(0, calldataload(0))
            case 0 { return(0, 4) }
            default { revert(0, 4) }
        }
    }
}

contract Destroyer {
    constructor() payable {}

    function kill(address payable beneficiary) external {
        selfdestruct(beneficiary);
    }
}

contract Depth {
    fallback() external {
        assembly {
            let target := calldataload(0)
            let current := calldataload(32)
            if eq(current, target) {
                mstore(0, current)
                mstore(32, 1)
                return(0, 64)
            }
            mstore(0, target)
            mstore(32, add(current, 1))
            let ok := call(gas(), address(), 0, 0, 64, 0, 64)
            if iszero(ok) {
                mstore(0, current)
                mstore(32, 0)
            }
            return(0, 64)
        }
    }
}
